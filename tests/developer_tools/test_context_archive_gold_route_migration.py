import json
from pathlib import Path

from scripts.developer_tools.context_archive_gold_route_migration import (
    _manifest_from_markdown,
    _transform_markdown,
)


def test_transform_markdown_separates_event_prose_from_supporting_text(tmp_path: Path):
    path = tmp_path / "gold.md"
    path.write_text(
        "\n".join([
            "generated_at: \"2026-08-03\"",
            "| `unit_0` | `event.1.name; event.1.desc` | `chain_a` | `primary_member` | event | `high` |",
            "| `unit_1` | `tech_reward; tech_reward_desc` | `chain_a` | `supporting_context` | reward | `high` |",
            "### `unit_1` · `tech_reward`",
            "- **relation：** `supporting_context`",
        ]) + "\n",
        encoding="utf-8",
    )

    assert _transform_markdown(path, {"unit_0"}, "2026-09-01") == 2

    text = path.read_text(encoding="utf-8")
    assert 'generated_at: "2026-09-01"' in text
    assert "| `unit_0` | `event.1.name; event.1.desc` | `chain_a` | `primary_member` |" in text
    assert "| `unit_1` | `tech_reward; tech_reward_desc` | `supporting_text` | `reference_asset` |" in text
    assert "原关联链：`chain_a`" in text
    assert "- **relation：** `reference_asset`" in text


def test_manifest_from_markdown_preserves_route_gold_identity(tmp_path: Path):
    markdown = tmp_path / "gold.md"
    manifest = tmp_path / "gold_manifest.json"
    markdown.write_text(
        "| `unit_0` | `event.1.name; event.1.desc` | `chain_a` | "
        "`primary_member` | event | `high` |\n",
        encoding="utf-8",
    )

    assert _manifest_from_markdown(
        markdown, "horizon-signal", "2026-09-01", manifest,
    ) == 1

    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert document["fixture"]["unit_count"] == 95
    assert document["assignments"][0]["item_keys"] == [
        "event.1.name", "event.1.desc",
    ]
    assert document["assignments"][0]["relation"] == "primary_member"
