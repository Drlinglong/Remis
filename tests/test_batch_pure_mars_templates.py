import json
import pytest

from scripts.core.batch_collection import collect_results
from scripts.core.batch_repository import BatchConflict
from scripts.schemas.agent_batch import BatchPlanRequest, BatchStartRequest
from tests.test_agent_batch_workflow import batch_environment


def collect(source, target):
    snapshot = {'game_id':'surviving_mars','adapter_id':'surviving_mars_csv','source_locale':'en',
                'files':[{'file_id':'file','selected':True,'entries':[{'id':'e','key':'1','source':source}]}]}
    requests = [{'custom_id':'request','entry_ids':['e']}]
    remote = {'results':[{'custom_id':'request','response':{'status_code':200,'body':{'choices':[
        {'finish_reason':'stop','message':{'content':json.dumps({'translations':{'e':target}})}}]}}}]}
    return collect_results(snapshot,requests,remote,'zh-TW')


def test_pure_layout_resource_template_is_preserved_without_false_source_fallback():
    source = "<style PGPropChoiceValue ><funding(used, 'no_style')> </style> / <funding(total, 'no_style')>"
    result = collect(source,source)
    assert result['translations']=={'e':source} and result['diagnostics']==[]
    assert result['complete_file_ids']==['file']


def test_real_english_and_changed_tokens_still_fail_review():
    source = "<em>Funding</em>: <funding(total)>"
    assert collect(source,source)['translations']=={}
    assert collect(source,source)['diagnostics'][0]['issues']==[{'code':'source_fallback_review_required'}]
    template = '<funding(total)> / <funding(used)>'
    result = collect(template,'<funding(total)>')
    assert result['translations']=={}
    assert any(i['code']=='token_integrity_error' for i in result['diagnostics'][0]['issues'])


@pytest.mark.asyncio
async def test_revalidate_uses_only_saved_raw_results_and_keeps_previous_collection(batch_environment):
    service = batch_environment['service']()
    plan = await service.plan(BatchPlanRequest(project_id='project-mars', file_ids=['source-1'],
        target_locale='zh-TW', game_language_slot='Schinese', model='fake/model', translation_context_mode='none'))
    job = await service.start(BatchStartRequest(plan_id=plan['id'], idempotency_key='revalidate', approved=True))
    await service.collect(job['id'])
    prior = service.artifacts.put({'parser_version':'older','translations':{},'diagnostics':[{'code':'old_check'}]})
    service.repository.update(job['id'],{'collection_artifact':prior})

    async def forbidden(*args):
        raise AssertionError('Revalidation must not call the provider')

    service.transport.retrieve = forbidden
    result = await service.collect(job['id'], revalidate=True)
    assert len(result['collection']['translations'])==2
    assert prior in result['collection_history']
    assert service.artifacts.get(prior)['diagnostics']==[{'code':'old_check'}]
    service.repository.update(job['id'],{'apply_status':'applied'})
    with pytest.raises(BatchConflict,match='already applied'):
        await service.collect(job['id'], revalidate=True)
