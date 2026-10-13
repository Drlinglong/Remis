"""Existing native language registrations must survive a source-copy export."""
import pytest

from scripts.core.mars_pipeline.delivery_metadata import (
    DeliveryMetadataError, _append_metadata_loctables,
)


def test_merge_preserves_existing_russian_registration_and_bom():
    original = ("return PlaceObj('ModDef', {'id', 'Grom', 'loctables', {"
                "{filename = 'Mod/Grom/local.csv', language = 'Russian'},"
                "}, 'default_options', {value = 'unchanged'},})")
    result = _append_metadata_loctables(b'\xef\xbb\xbf' + original.encode('utf-8'), 'Grom', [
        {'language': 'Schinese', 'path': 'Localization/Schinese/ModTexts.csv'}
    ])
    assert result.startswith(b'\xef\xbb\xbf')
    text = result.decode('utf-8-sig')
    assert text.count("'loctables'") == 1
    assert "{filename = 'Mod/Grom/local.csv', language = 'Russian'}," in text
    assert 'Mod/Grom/Localization/Schinese/ModTexts.csv' in text
    assert "'default_options', {value = 'unchanged'}" in text


@pytest.mark.parametrize('value', [
    'GetTables()', '{GetTable()}',
    "{{filename = GetPath(), language = 'Russian'}}",
    "{{filename = 'local.csv', language = 'Russian', unexpected = 'x'}}",
    "{{filename = 'local.csv'}}",
    "{{filename = 'a', filename = 'b', language = 'Russian'}}",
])
def test_merge_rejects_dynamic_or_ambiguous_existing_registrations(value):
    source = f"return PlaceObj('ModDef', {{'id', 'Grom', 'loctables', {value},}})"
    with pytest.raises(DeliveryMetadataError):
        _append_metadata_loctables(source.encode('utf-8'), 'Grom', [])
