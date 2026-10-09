"""Prepare read-only corpus/reference inputs, then import through Remis Agent API."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("english", type=Path)
    parser.add_argument("schinese", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base", default="http://127.0.0.1:1456")
    args = parser.parse_args()
    def api(path, payload=None):
        request = urllib.request.Request(args.base + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(request, timeout=180))
    assert api("/api/agent/preflight")["status"] == "ready"
    with args.schinese.open(encoding="utf-8-sig", newline="") as stream:
        references = {r[0]: r for r in csv.reader(stream) if len(r) > 11 and r[0].isascii() and r[0].isdecimal()}
    rows = [["ID", "Text", "Translation", "VoiceActor", "Context"]]
    matches, missing = 0, 0
    with args.english.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream):
            if len(row) <= 11 or not row[0].isascii() or not row[0].isdecimal() or not row[1].strip():
                continue
            ref = references.get(row[0])
            matched = bool(ref and ref[1] == row[1] and ref[2].strip())
            rows.append([row[0], row[1], ref[2] if matched else "", row[3], row[11]])
            matches += matched
            missing += not matched
    assert len({row[0] for row in rows[1:]}) == len(rows) - 1
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\r\n").writerows(rows)
    content = stream.getvalue().encode("utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / "Game.csv"
    if target.exists():
        assert target.read_bytes() == content, "Never replace a prepared corpus"
    else:
        target.write_bytes(content)
    provenance = {"source_english": str(args.english), "english_sha256": hashlib.sha256(args.english.read_bytes()).hexdigest(),
        "reference_schinese": str(args.schinese), "schinese_sha256": hashlib.sha256(args.schinese.read_bytes()).hexdigest(),
        "entry_count": len(rows) - 1, "matched_references": matches, "unmatched_or_empty_references": missing,
        "prepared_sha256": hashlib.sha256(content).hexdigest()}
    (args.output.parent / "coverage-input-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    inspection = api("/api/agent/projects/inspect", {"folder_path": str(args.output), "game_id": "surviving_mars", "source_language": "en"})
    assert not inspection["inspection"]["game_support"]["has_blocking_diagnostics"]
    plan = api("/api/agent/projects/plan", {"folder_path": str(args.output), "game_id": "surviving_mars",
        "source_language": "en", "name": "Mars English corpus and official SC reference - coverage", "import_mode": "copy"})
    (args.output.parent / "coverage-import-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"plan_id": plan["plan_id"], **provenance}, ensure_ascii=True))


if __name__ == "__main__":
    main()
