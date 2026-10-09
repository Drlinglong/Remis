"""Freeze a reproducible stratified Mars trial; never change managed projects."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


SEED = "mars-tw-luna-trial-20261006-v1"


def bucket(text):
    return "short" if len(text) <= 80 else "medium" if len(text) <= 350 else "long"


def category(context):
    if context.startswith("Tech "):
        return "technology"
    if context.startswith("StoryBit "):
        return "events"
    if context.startswith(("Tutorial ", "TutorialStep ", "OnScreenHint ")) or (
        context.startswith("PopupNotificationPreset ") and "Tutorial" in context
    ):
        return "tutorial"
    if context.startswith("EncyclopediaArticle "):
        return "encyclopedia"
    if context.startswith(("TraitPreset ", "BuildingTemplate ", "Resource ", "ResourceIngredient ")):
        return "labels"
    return None


def rank(row):
    return hashlib.sha256((SEED + ":" + row["source_id"]).encode("utf-8")).hexdigest()


def select(rows, quotas, required=()):
    selected = [row for row in rows if row["source_id"] in required]
    for name, amount in quotas.items():
        existing = sum(row["length_bucket"] == name for row in selected)
        candidates = sorted((row for row in rows if row not in selected and row["length_bucket"] == name), key=rank)
        selected.extend(candidates[:max(0, amount - existing)])
    count = sum(quotas.values())
    if len(selected) < count:
        selected.extend(sorted((row for row in rows if row not in selected), key=rank)[:count - len(selected)])
    if len(selected) != count:
        raise ValueError("The candidate pool cannot satisfy the exact trial scope")
    return sorted(selected, key=lambda row: (len(row["source"]), rank(row)))


def write_tables(root, rows):
    root.mkdir(parents=True, exist_ok=False)
    for name in dict.fromkeys(row["category"] for row in rows):
        with (root / (name + ".csv")).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ID", "Text", "Translation", "VoiceActor", "Context"])
            for row in rows:
                if row["category"] == name:
                    writer.writerow([row["source_id"], row["source"], "", "", row["context"]])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    pools = {name: [] for name in ("technology", "events", "tutorial", "encyclopedia", "labels")}
    seen = set()
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.reader(handle):
            if len(raw) < 12 or not raw[0].isdigit() or raw[0] in seen:
                continue
            text, context = raw[1], raw[11]
            name = category(context)
            if not name or not text.strip() or not any(char.isalpha() for char in text):
                continue
            if name == "labels" and not any(token in context for token in ("display_name", "DisplayName")):
                continue
            if name == "technology" and not any(token in context for token in ("Description", "DisplayName", "flavor")):
                continue
            seen.add(raw[0])
            pools[name].append({"source_id": raw[0], "source": text, "context": context,
                                "category": name, "length_bucket": bucket(text), "characters": len(text)})
    configuration = {
        "technology": ({"short": 7, "medium": 10, "long": 8}, ["6574", "6545", "6586", "6595", "6598", "794992500930", "625972098245"]),
        "events": ({"short": 8, "medium": 10, "long": 7}, []),
        "tutorial": ({"short": 5, "medium": 10, "long": 5}, []),
        "encyclopedia": ({"short": 4, "medium": 6, "long": 10}, ["404077228849"]),
        "labels": ({"short": 10}, []),
    }
    selected = []
    subset = []
    for name, (quotas, required) in configuration.items():
        group = select(pools[name], quotas, required)
        selected.extend(group)
        subset.extend(select(group, {"short": 3, "medium": 4, "long": 3} if name in ("technology", "events")
                             else {"short": 2, "medium": 3, "long": 3} if name in ("tutorial", "encyclopedia")
                             else {"short": 4}))
    assert len(selected) == 100 and len(subset) == 40
    assert {row["source_id"] for row in subset} <= {row["source_id"] for row in selected}
    args.destination.mkdir(parents=True, exist_ok=False)
    write_tables(args.destination / "source-100", selected)
    write_tables(args.destination / "source-40", subset)
    manifest = {"schema": "mars-trial-sample/1", "seed": SEED, "source_path": str(args.source),
                "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(), "source_column": "Text",
                "term_release_id": "terms_2b0191f02045f3a5f82cbeab", "gold_translations_sent": False,
                "sample_100": selected, "batch_40": subset,
                "category_counts": dict(Counter(row["category"] for row in selected)),
                "length_counts": dict(Counter(row["length_bucket"] for row in selected))}
    (args.destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("category_counts", "length_counts", "source_sha256")}))


if __name__ == "__main__":
    main()
