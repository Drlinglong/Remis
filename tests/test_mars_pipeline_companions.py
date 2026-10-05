"""Focused checks for text-only companion row ownership and conflicts."""

import pytest

from scripts.core.mars_pipeline.workflow_delivery_companions import (
    _merge_rows, _render_bundle, build_bundle,
)


def test_identical_companion_rows_share_conditional_ownership():
    rows = {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon-a"}}}
    _merge_rows(rows, {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon-b"}}})
    assert rows["42"]["owners"] == {"addon-a", "addon-b"}


@pytest.mark.parametrize("field", ["source", "target"])
def test_conflicting_companion_rows_fail_closed(field):
    rows = {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon-a"}}}
    incoming = {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon-b"}}}
    incoming["42"][field] = "Changed"
    with pytest.raises(ValueError, match=f"Companion {field} conflict for translation ID 42"):
        _merge_rows(rows, incoming)


def test_base_ids_must_be_approved_existing_rows_before_deduplication():
    receipt = {"manifest": {"mod_id": "base", "approved_ids": [], "entries": {
        "42": {"kind": "literal", "text": "Same source"},
    }}}
    rows = {"zh-CN": {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon"}}}}
    with pytest.raises(ValueError, match="Base/companion ID conflict for translation ID 42"):
        _render_bundle(receipt, {"zh-CN": {}}, rows, [])


def test_base_target_exact_duplicate_is_deduplicated_from_conditional_table():
    receipt = {"manifest": {"mod_id": "base", "approved_ids": ["42"], "entries": {
        "42": {"kind": "existing_t", "text": "Same source"},
    }}}
    rows = {"zh-CN": {"42": {"source": "Same source", "target": "同一译文", "owners": {"addon"}}}}
    bundle = _render_bundle(receipt, {"zh-CN": {"42": "同一译文"}}, rows, [])
    assert bundle["files"] == {}
    assert bundle["localized_ids"] == []


@pytest.mark.asyncio
async def test_bundle_places_addon_ids_in_conditional_table_and_freezes_snapshots(monkeypatch):
    from scripts.core.mars_pipeline import delivery, workflow_delivery

    base_receipt = {"project_id": "base-project", "manifest": {
        "mod_id": "base-mod", "approved_ids": ["1"],
        "entries": {"1": {"kind": "existing_t", "text": "Base source"}},
    }}
    companion_receipt = {"project_id": "addon-project", "run_id": "addon-run",
                         "source_path": ".", "manifest": {
        "mod_id": "addon-mod", "approved_ids": ["42"],
        "entries": {"42": {"kind": "existing_t", "text": "Addon source"}},
    }}

    async def context(_project_id):
        return {"game_id": "surviving_mars"}, companion_receipt

    monkeypatch.setattr(workflow_delivery, "_context", context)
    monkeypatch.setattr(workflow_delivery, "_read_translations", lambda *_args: {"zh-CN": {"42": "附加译文"}})
    monkeypatch.setattr(delivery, "inspect_delivery", lambda *_args: {
        "source_fingerprint": "source-snapshot", "fingerprint": "output-snapshot",
    })
    outputs = [{"project_id": "addon-project", "language_code": "zh-CN",
                "output_folder_name": "zh-CN-addon"}]
    bundle = await build_bundle("base-project", base_receipt, {"zh-CN": {"1": "基础译文"}}, outputs)

    assert bundle["localized_ids"] == ["42"]
    assert "42,Addon source,附加译文" in next(iter(bundle["files"].values())).decode("utf-8")
    loader = bundle["loader"].decode("utf-8")
    assert "enabled[owner]" in loader
    assert "addon-mod" in loader and "42" in loader
    assert bundle["snapshots"][0]["source_fingerprint"] == "source-snapshot"
    assert bundle["snapshots"][0]["output_fingerprint"] == "output-snapshot"

    changed = [dict(bundle["snapshots"][0], output_fingerprint="changed-output")]
    with pytest.raises(ValueError, match="changed after preview"):
        await build_bundle("base-project", base_receipt, {"zh-CN": {"1": "基础译文"}},
                           outputs, expected_snapshots=changed)
