"""Freeze the existing 40 IDs with related English context and import via Remis."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request


def api(base, path, payload=None):
    request = urllib.request.Request(base + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(request, timeout=180))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def related_context(row, all_rows):
    parts = row[11].split()
    if len(parts) < 3 or parts[0] not in {"Tech", "StoryBit"}:
        return row[11], []
    prefix = " ".join(parts[:2]) + " "
    siblings = [item for item in all_rows if item[0] != row[0] and item[11].startswith(prefix)]
    if parts[0] == "Tech":
        related = [item for item in siblings if item[11].split()[-1] in {"DisplayName", "Description", "flavor"}]
    else:
        related = [item for item in siblings if item[11].split()[-1] == "Title"]
        line = lambda item: int(re.search(r"\((\d+)\)$", item[10]).group(1)) if re.search(r"\((\d+)\)$", item[10]) else -1
        preceding = [item for item in siblings if item[11].split()[-1] == "VoicedText" and 0 <= line(item) < line(row)]
        if preceding:
            related.append(max(preceding, key=line))
    unique = {item[0]: {"source_id": item[0], "source": item[1], "context": item[11]} for item in related}
    values = list(unique.values())
    return json.dumps({"object_context": row[11], "related_english_source": values}, ensure_ascii=False), values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--base", default="http://127.0.0.1:1456")
    args = parser.parse_args()
    args.root.mkdir(exist_ok=True)
    preflight = api(args.base, "/api/agent/preflight")
    save_json(args.root / "preflight.json", preflight)
    assert preflight["status"] == "ready"
    original = json.loads((args.baseline / "manifest.json").read_text(encoding="utf-8"))
    source_path = Path(original["source_path"])
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == original["source_sha256"]
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        all_rows = [row for row in csv.reader(stream) if len(row) > 11]
    source = {row[0]: row for row in all_rows}
    selected, grouped = [], {}
    for entry in original["batch_40"]:
        row = source[entry["source_id"]]
        assert row[1] == entry["source"]
        context, related = related_context(row, all_rows)
        selected.append({**entry, "model_context": context, "related_english_source": related})
        grouped.setdefault(entry["category"], []).append([row[0], row[1], "", "", context])
    assert len(selected) == 40
    manifest = {"schema": "mars-model-comparison/2", "baseline_manifest": str(args.baseline / "manifest.json"),
                "source_sha256": original["source_sha256"], "entries": selected,
                "gold_translations_sent": False, "context_policy": "same-object tech title/description/flavor; story title and nearest earlier voiced text"}
    hashes = {}
    for category, rows in grouped.items():
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(["ID", "Text", "Translation", "VoiceActor", "Context"])
        writer.writerows(rows)
        content = stream.getvalue()
        for parent in [args.root / "source-40-context", args.input_dir]:
            parent.mkdir(parents=True, exist_ok=True)
            target = parent / (category + ".csv")
            encoded = content.encode("utf-8")
            if target.exists():
                assert target.read_bytes() == encoded, "Existing sample must never be overwritten"
            else:
                target.write_bytes(encoded)
        hashes[category + ".csv"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest["file_hashes"] = hashes
    save_json(args.root / "manifest.json", manifest)
    inspection = api(args.base, "/api/agent/projects/inspect", {"folder_path": str(args.input_dir), "game_id": "surviving_mars", "source_language": "en"})
    save_json(args.root / "inspection.json", inspection)
    plan = api(args.base, "/api/agent/projects/plan", {"folder_path": str(args.input_dir), "game_id": "surviving_mars",
        "source_language": "en", "name": "Mars TW model comparison v2 - 40 entries", "import_mode": "copy"})
    save_json(args.root / "project-import-plan.json", plan)
    print(json.dumps({"plan_id": plan.get("plan_id"), "entries": 40,
                      "context_enriched_entries": sum(bool(item["related_english_source"]) for item in selected)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
