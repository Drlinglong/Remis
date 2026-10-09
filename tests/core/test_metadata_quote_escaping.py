"""Descriptor names stay valid Paradox script when translations contain quotes."""

from types import SimpleNamespace

import pytest

from scripts.core.asset_handler import _process_eu4_metadata, _process_stellaris_metadata


@pytest.mark.parametrize("processor, encoding", [
    (_process_stellaris_metadata, "utf-8"),
    (_process_eu4_metadata, "utf-8-sig"),
])
def test_descriptor_name_escapes_inner_quotes(tmp_path, processor, encoding):
    source = tmp_path / "source"
    source.mkdir()
    (source / "descriptor.mod").write_text('name="Old Name"\nversion="1.0"\n', encoding="utf-8")
    handler = SimpleNamespace(translate_single_text=lambda *args: 'The "New" Dawn')

    processor(
        "Demo", handler, {"code": "en"},
        {"code": "custom", "key": "l_custom", "name": "Custom"},
        "out", "", {"metadata_file": "descriptor.mod"},
        source_mod_path=str(source), dest_base_dir=str(tmp_path),
    )

    descriptor = (tmp_path / "out" / "descriptor.mod").read_text(encoding=encoding)
    assert 'name="The \\"New\\" Dawn (Custom Translation)"' in descriptor
