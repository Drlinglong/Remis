import json
from pathlib import Path

from scripts.core.paradox_localization_parser import parse_text


ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "assets" / "release_demo_content" / "demos" / "Test_Project_Remis_Vic3"


def test_vic3_demo_reference_reuse_smoke_manifest_matches_source():
    manifest = json.loads(
        (DEMO_ROOT / ".metadata" / "reference_reuse_smoke.json").read_text(encoding="utf-8")
    )
    source_path = DEMO_ROOT / manifest["source_file"]
    report = parse_text(source_path.read_text(encoding="utf-8-sig"))
    source_by_key = {entry.base_key: entry.value for entry in report.entries}

    assert report.diagnostics == ()
    assert {key: source_by_key[key] for key in manifest["expected_reused"]} == {
        "FRA": "法兰西",
        "GBR": "大不列颠",
        "TRK": "图尔卡纳",
        "TUR": "土耳其",
        "USA": "美利坚",
    }
    assert source_by_key[manifest["expected_model_submitted"][0]] == "图尔卡纳"
