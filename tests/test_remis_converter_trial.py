import pytest

from scripts.developer_tools.remis_converter_trial import align_peer, conversion_payload, parse_conversion


def test_converter_keeps_semantic_tokens_visible_and_disables_layout_cleanup():
    payload = conversion_payload('<em>设备</em>生产<resource(Metals)>。\\n剩余<percent(n)>')
    assert payload['text'] == '<em>设备</em>生产<resource(Metals)>。\\n剩余<percent(n)>'
    assert {'<em>', '</em>', '<resource(Metals)>', '<percent(n)>', r'\n'} <= set(payload['userProtectReplace'].splitlines())
    assert payload['cleanUpText'] is False
    assert payload['ensureNewlineAtEof'] is False
    assert payload['userPostReplace'] == payload['userPreReplace'] == ''


def test_peer_alignment_rejects_same_id_changed_english_and_missing_translation():
    entries = [{'id': 'review-1', 'key': '123', 'source': 'Asteroid'}]
    snapshot = {'files': [{'entries': [{'id': 'source-1', 'key': '123', 'source': 'Asteroid'}]}]}
    assert align_peer(entries, snapshot, {'translations': {'source-1': '小行星'}}) == {'review-1': '小行星'}
    with pytest.raises(ValueError):
        align_peer(entries, snapshot, {'translations': {}})
    snapshot['files'][0]['entries'][0]['source'] = 'Planet'
    with pytest.raises(ValueError):
        align_peer(entries, snapshot, {'translations': {'source-1': '小行星'}})


def test_converter_empty_failed_and_wrong_mode_outputs_are_not_valid_candidates():
    assert parse_conversion({'code': 0, 'data': {'converter': 'Taiwan', 'text': '小行星'}}) == '小行星'
    for value in [{'code': 1, 'msg': 'failed'}, {'code': 0, 'data': {'converter': 'Taiwan', 'text': ''}},
                  {'code': 0, 'data': {'converter': 'Traditional', 'text': '小行星'}}]:
        with pytest.raises(ValueError):
            parse_conversion(value)
