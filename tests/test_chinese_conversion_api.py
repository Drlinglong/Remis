import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.batch_artifacts import BatchArtifacts
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.chinese_conversion_service import ChineseConversionService, payload_for
from scripts.routers import agent_chinese_conversion as routes
from scripts.schemas.chinese_conversion import ChineseConversionRequest


class Wire:
    calls = 0
    mode = 'valid'

    async def info(self):
        return {'data': {'converters': {'Taiwan': {}}, 'modules': {}}, 'revisions': {'build': 'test'}}

    async def convert(self, payload):
        self.calls += 1
        if self.mode == 'transport_failure':
            raise TimeoutError('simulated interrupted response')
        values = json.loads(payload['text'])
        values = [v.replace('视频', '影片').replace('设备', '設備') for v in values]
        if self.mode == 'token_loss':
            values[0] = values[0].replace('<resource(Metals)>', '')
        if self.mode == 'wrong_count':
            values.pop()
        return {'http_status': 200, 'raw_body': 'retained raw response', 'body': {'code': 0,
            'data': {'converter': 'Taiwan', 'text': json.dumps(values)}, 'revisions': {'build': 'test'}}}


def environment(tmp_path):
    wire = Wire()
    repository = BatchRepository(tmp_path / 'ledger.sqlite')
    artifacts = BatchArtifacts(tmp_path / 'artifacts')
    service = ChineseConversionService(repository, artifacts, wire)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.service] = lambda: service
    return wire, service, TestClient(app)


def request(**changes):
    return {'entries': [{'id': '001', 'text': '<em>设备</em><resource(Metals)>\n视频'}],
            'idempotency_key': 'business-1', 'approved': True, **changes}


def test_api_retains_artifacts_and_same_key_reuses_after_restart(tmp_path):
    wire, service, client = environment(tmp_path)
    result = client.post('/api/agent/chinese-conversion/convert', json=request()).json()
    assert result['status'] == 'completed'
    assert result['result']['entries'][0]['text'] == '<em>設備</em><resource(Metals)>\n影片'
    assert result['automatic_apply'] is False and result['result']['language_certified'] is False
    assert wire.calls == 1
    assert client.post('/api/agent/chinese-conversion/convert', json=request()).json()['id'] == result['id']
    restarted = ChineseConversionService(BatchRepository(tmp_path/'ledger.sqlite'), BatchArtifacts(tmp_path/'artifacts'), wire)
    assert restarted.get(result['id'])['result'] == result['result']
    assert client.get(f"/api/agent/chinese-conversion/jobs/{result['id']}/artifacts/response").json()['raw_body'] == 'retained raw response'
    assert len(client.get('/api/agent/chinese-conversion/jobs').json()['jobs']) == 1
    assert wire.calls == 1


def test_unknown_submission_does_not_replay_and_other_kinds_are_not_readable(tmp_path):
    wire, service, client = environment(tmp_path)
    wire.mode = 'transport_failure'
    first = client.post('/api/agent/chinese-conversion/convert', json=request()).json()
    assert first['status'] == 'failed' and first['submission_may_have_been_accepted']
    client.post('/api/agent/chinese-conversion/convert', json=request())
    assert wire.calls == 1
    assert client.post('/api/agent/chinese-conversion/convert', json=request(entries=[{'id': '001','text':'Different'}])).status_code == 409
    service.repository.put('job', {'id':'foreign','project_id':'project'})
    assert client.get('/api/agent/chinese-conversion/jobs/foreign').status_code == 404
    assert client.get(f"/api/agent/chinese-conversion/jobs/{first['id']}/artifacts/arbitrary_path").status_code == 404


def test_changed_tokens_and_count_failures_preserve_raw_evidence(tmp_path):
    wire, service, client = environment(tmp_path)
    wire.mode = 'token_loss'
    first = client.post('/api/agent/chinese-conversion/convert', json=request()).json()
    assert first['status'] == 'completed_with_errors' and first['result']['valid_count'] == 0
    assert first['result']['entries'][0]['diagnostics'] == ['semantic_token_order_or_identity_changed']
    wire.mode = 'wrong_count'
    second = client.post('/api/agent/chinese-conversion/convert', json=request(idempotency_key='new', entries=[{'id':'002','text':'视频'}])).json()
    assert second['status'] == 'failed' and second['error_code'] == 'conversion_output_count_or_empty'
    assert service.artifact(second['id'],'response')['raw_body']


def test_schema_does_not_silently_accept_llm_instructions_or_unsafe_rules(tmp_path):
    wire, service, client = environment(tmp_path)
    assert client.post('/api/agent/chinese-conversion/convert', json=request(approved=False)).status_code == 409
    for changes in [{'instructions':'Translate as a poet'}, {'term_release_id':'terms'},
                    {'post_replace':{'a=b':'x'}}, {'entries':[{'id':'1','text':'a'},{'id':'1','text':'b'}]}]:
        assert client.post('/api/agent/chinese-conversion/convert',json=request(**changes)).status_code == 422
    assert wire.calls == 0


def test_decorative_angle_brackets_do_not_protect_chinese_display_text():
    value = ChineseConversionRequest(**request(entries=[{'id':'label','text':'<<< 新存档 >>> <em>选择</em>'}]))
    protected = payload_for(value)['userProtectReplace'].splitlines()
    assert '< 新存档 >' not in protected
    assert {'<em>', '</em>'} <= set(protected)


def test_chinese_bracket_labels_are_convertible_but_script_expressions_are_protected():
    value = ChineseConversionRequest(**request(entries=[{'id':'label','text':'[无可用火箭] [Root.GetName] <duration>'}]))
    protected = payload_for(value)['userProtectReplace'].splitlines()
    assert '[无可用火箭]' not in protected
    assert {'[Root.GetName]', '<duration>'} <= set(protected)
