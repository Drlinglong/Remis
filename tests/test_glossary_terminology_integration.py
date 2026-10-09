"""Real main-DB CRUD and immutable snapshots, without provider calls."""
import asyncio

import pytest
import pytest_asyncio
from sqlmodel import SQLModel

from scripts.core.batch_artifacts import BatchArtifacts
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.db_manager import db_manager
from scripts.core.glossary_manager import GlossaryManager
from scripts.core.glossary_terminology_service import GlossaryTerminologyService, glossary_languages, review_basis
from scripts.core.term_release_service import TermReleaseService
from scripts.routers.glossary import _transform_storage_to_frontend_format
from scripts.schemas.glossary_terminology import GlossaryTermReleaseRequest, TerminologyGlossaryImport
from scripts.schemas.glossary_terminology import GlossaryTermReviewRequest
from scripts.schemas.glossary_terminology import GlossaryTermAppendRequest


@pytest_asyncio.fixture
async def environment(tmp_path):
    old_path = db_manager.db_path
    await db_manager.close_async_engine()
    db_manager.db_path = str(tmp_path / 'main.sqlite')
    engine = db_manager.get_async_engine()
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    releases = TermReleaseService(BatchRepository(tmp_path / 'batch.sqlite'), BatchArtifacts(tmp_path / 'artifacts'))
    bridge = GlossaryTerminologyService(db_manager, releases)
    yield bridge, GlossaryManager(), releases
    await db_manager.close_async_engine()
    db_manager.db_path = old_path


def import_request(**updates):
    payload = {'game_id': 'surviving_mars', 'locale': 'zh-TW', 'name': 'Review terms',
        'import_key': 'source-test-v1', 'approved': True, 'terms': [
            {'concept_id': 'mars:water:1', 'source_id': '1', 'source': 'Water', 'translation': '水量',
             'reference_translations': {'zh-CN': '水资源'}, 'sense': 'Terraforming percentage',
             'context_keys': ['source_id:1'], 'review_state': 'reviewed', 'confidence': 'high'},
            {'concept_id': 'mars:water:2', 'source_id': '2', 'source': 'Water', 'translation': '水資源',
             'sense': 'Stored resource', 'context_keys': ['source_id:2'], 'review_state': 'candidate'},
            {'concept_id': 'mars:idiot:3', 'source_id': '3', 'source': 'Idiot', 'translation': '笨蛋',
             'sense': 'Trait tone choice', 'review_state': 'pending', 'confidence': 'low'},
        ]}
    return TerminologyGlossaryImport.model_validate({**payload, **updates})


def freeze_request(preview, **updates):
    return GlossaryTermReleaseRequest.model_validate({'glossary_id': preview['glossary_id'],
        'locale': 'zh-TW', 'version': '1', 'expected_fingerprint': preview['fingerprint'],
        'approved': True, **updates})


@pytest.mark.asyncio
async def test_append_preserves_existing_editor_terms_and_frozen_release(environment):
    bridge, manager, releases = environment
    preview = await bridge.import_glossary(import_request())
    old = await bridge.publish(freeze_request(preview))
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    before = {row['entry_id']: row for row in page['entries']}
    payload = {'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint'], 'approved': True,
        'terms': [{'concept_id': 'mars:renegade:4368', 'source': 'Renegade', 'translation': '叛逆者',
            'sense': 'Colonist crime trait, not a colonist leaving Mars', 'aliases': ['Renegades']}]}
    with pytest.raises(BatchConflict) as error:
        await bridge.append(preview['glossary_id'], GlossaryTermAppendRequest.model_validate({**payload, 'approved': False}))
    assert error.value.code == 'approval_required'
    updated = await bridge.append(preview['glossary_id'], GlossaryTermAppendRequest.model_validate(payload))
    assert updated['entry_count'] == preview['entry_count'] + 1
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    assert all(row == before[row['entry_id']] for row in page['entries'] if row['entry_id'] in before)
    with pytest.raises(BatchConflict) as error:
        await bridge.append(preview['glossary_id'], GlossaryTermAppendRequest.model_validate(payload))
    assert error.value.code == 'glossary_changed'
    payload['expected_fingerprint'] = updated['fingerprint']
    with pytest.raises(BatchConflict) as error:
        await bridge.append(preview['glossary_id'], GlossaryTermAppendRequest.model_validate(payload))
    assert error.value.code == 'duplicate_concept_id'
    payload.update(locale='fr')
    with pytest.raises(BatchConflict) as error:
        await bridge.append(preview['glossary_id'], GlossaryTermAppendRequest.model_validate(payload))
    assert error.value.code == 'terminology_locale_conflict'
    new = await bridge.publish(freeze_request(updated, version='2'))
    assert any(term['source'] == 'Renegade' and term['aliases'] == ['Renegades'] for term in releases.get(new['id'])[1])
    assert all(term['source'] != 'Renegade' for term in releases.get(old['id'])[1])


async def edit_translation(manager, glossary_id, entry_id, translation):
    page = await manager.get_glossary_entries_paginated(glossary_id, 1, 100)
    stored = next(row for row in page['entries'] if row['entry_id'] == entry_id)
    stored['translations']['zh-TW'] = translation
    assert await manager.update_entry(entry_id, {'translations': stored['translations'],
        'metadata': stored['raw_metadata'], 'variants': stored['variants'], 'abbreviations': stored['abbreviations']})


@pytest.mark.asyncio
async def test_existing_tree_and_editor_see_all_terms_with_distinct_senses(environment):
    bridge, manager, _ = environment
    preview = await bridge.import_glossary(import_request())
    assert preview['entry_count'] == 3 and preview['eligible_count'] == 2
    assert preview['review_states'] == {'reviewed': 1, 'candidate': 1, 'pending': 1}
    tree = await manager.get_glossary_tree_data()
    assert any(str(preview['glossary_id']) == child['key'].split('|')[1]
               for game in tree for child in game.get('children', []))
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    rows = [_transform_storage_to_frontend_format(row) for row in page['entries']]
    water = [row for row in rows if row['source'] == 'Water']
    assert len(water) == 2 and water[0]['id'] != water[1]['id']
    assert any(row['translations'].get('zh-CN') == '水资源' for row in water)
    assert any(row['metadata']['terminology']['review_state'] == 'pending' for row in rows)


@pytest.mark.asyncio
async def test_repeat_import_does_not_overwrite_user_edits_or_resurrect_deleted_rows(environment):
    bridge, manager, _ = environment
    request = import_request()
    preview = await bridge.import_glossary(request)
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    entry = page['entries'][0]
    await edit_translation(manager, preview['glossary_id'], entry['entry_id'], '人工修订')
    assert await manager.delete_entry(page['entries'][1]['entry_id'])
    repeated = await bridge.import_glossary(request)
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    assert repeated['glossary_id'] == preview['glossary_id'] and repeated['entry_count'] == 2
    assert any(row['translations']['zh-TW'] == '人工修订' for row in page['entries'])
    with pytest.raises(BatchConflict, match='import key'):
        await bridge.import_glossary(import_request(name='Changed import'))


@pytest.mark.asyncio
async def test_parallel_imports_create_one_glossary(environment):
    bridge, manager, _ = environment
    first, second = await asyncio.gather(bridge.import_glossary(import_request()), bridge.import_glossary(import_request()))
    assert first['glossary_id'] == second['glossary_id']
    assert len(await manager.get_available_glossaries('surviving_mars')) == 1


@pytest.mark.asyncio
async def test_snapshot_stays_frozen_after_normal_editor_crud_and_pending_is_excluded(environment):
    bridge, manager, releases = environment
    preview = await bridge.import_glossary(import_request())
    release = await bridge.publish(freeze_request(preview))
    original = releases.get(release['id'])[1]
    assert len(original) == 2 and all(term['source'] == 'Water' for term in original)
    assert release['origin']['glossary_id'] == preview['glossary_id']
    assert len(release['origin']['excluded']) == 1
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    reviewed = next(row for row in page['entries'] if row['raw_metadata']['terminology']['review_state'] == 'reviewed')
    await edit_translation(manager, preview['glossary_id'], reviewed['entry_id'], '修改过的水量')
    assert releases.get(release['id'])[1] == original
    with pytest.raises(BatchConflict) as changed:
        await bridge.publish(freeze_request(preview, version='2'))
    assert changed.value.code == 'glossary_changed'
    current = await bridge.preview(preview['glossary_id'], 'zh-TW')
    assert current['review_states'] == {'candidate': 2, 'pending': 1}
    updated = await bridge.publish(freeze_request(current, version='2'))
    assert any(term['translation'] == '修改过的水量' for term in releases.get(updated['id'])[1])


@pytest.mark.asyncio
async def test_approved_release_requires_current_explicit_reviews_and_correct_locale(environment):
    bridge, manager, releases = environment
    preview = await bridge.import_glossary(import_request())
    with pytest.raises(BatchConflict) as unapproved:
        await bridge.publish(freeze_request(preview, maturity='approved'))
    assert unapproved.value.code == 'unapproved_glossary_terms'
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    for row in page['entries']:
        detail = row['raw_metadata']['terminology']
        if detail['review_state'] == 'pending':
            continue
        detail['review_state'] = 'approved'
        detail['review_basis'] = review_basis(row['translations']['en'], row['translations']['zh-TW'], detail)
        assert await manager.update_entry(row['entry_id'], {'translations': row['translations'], 'metadata': row['raw_metadata']})
    preview = await bridge.preview(preview['glossary_id'], 'zh-TW')
    assert (await bridge.publish(freeze_request(preview, maturity='approved')))['maturity'] == 'approved'
    with pytest.raises(BatchConflict) as wrong_locale:
        await bridge.preview(preview['glossary_id'], 'zh-CN')
    assert wrong_locale.value.code == 'terminology_locale_conflict'


@pytest.mark.asyncio
async def test_no_permission_or_duplicate_identity_leaves_main_db_untouched(environment):
    bridge, manager, _ = environment
    with pytest.raises(BatchConflict):
        await bridge.import_glossary(import_request(approved=False))
    request = import_request()
    request.terms[1].concept_id = request.terms[0].concept_id
    with pytest.raises(BatchConflict) as duplicate:
        await bridge.import_glossary(request)
    assert duplicate.value.code == 'duplicate_concept_id'
    assert await manager.get_available_glossaries('surviving_mars') == []


def test_glossary_only_locale_does_not_claim_a_game_language_slot():
    languages = {'1': {'code': 'en', 'name': 'English', 'key': 'l_english'}}
    result = glossary_languages(languages)
    assert result['zh-TW']['name_local'] == '正體中文'
    assert 'key' not in result['zh-TW'] and 'zh-TW' not in languages


@pytest.mark.asyncio
async def test_human_review_is_atomic_and_preserves_model_evidence(environment):
    bridge, manager, _ = environment
    preview = await bridge.import_glossary(import_request())
    payload = {'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint'], 'reviewer': '玲珑',
        'approved': True, 'changes': [{'concept_id': 'mars:idiot:3', 'translation': '愚鈍',
            'review_state': 'approved', 'reason': 'User chooses the less colloquial trait name'}]}
    updated = await bridge.review(preview['glossary_id'], GlossaryTermReviewRequest.model_validate(payload))
    assert updated['eligible_count'] == 3 and updated['review_states']['approved'] == 1
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    row = next(item for item in page['entries'] if item['translations']['en'] == 'Idiot')
    detail = row['raw_metadata']['terminology']
    assert row['translations']['zh-TW'] == '愚鈍' and detail['original_candidate'] == ''
    assert detail['human_review']['reviewer'] == '玲珑'
    assert detail['human_review']['previous_translation'] == '笨蛋'
    with pytest.raises(BatchConflict) as stale:
        await bridge.review(preview['glossary_id'], GlossaryTermReviewRequest.model_validate(payload))
    assert stale.value.code == 'glossary_changed'
    payload['expected_fingerprint'] = updated['fingerprint']
    payload['changes'] += [{'concept_id': 'unknown', 'review_state': 'approved'}]
    with pytest.raises(BatchConflict):
        await bridge.review(preview['glossary_id'], GlossaryTermReviewRequest.model_validate(payload))
    assert (await bridge.preview(preview['glossary_id'], 'zh-TW'))['fingerprint'] == updated['fingerprint']


@pytest.mark.asyncio
async def test_alias_review_shared_editor_snapshot_and_stale_approval(environment):
    bridge, manager, releases = environment
    preview = await bridge.import_glossary(import_request())
    old_release = await bridge.publish(freeze_request(preview))
    request = GlossaryTermReviewRequest.model_validate({'locale': 'zh-TW',
        'expected_fingerprint': preview['fingerprint'], 'reviewer': 'User-authorized alias update',
        'approved': True, 'changes': [{'concept_id': 'mars:water:2', 'aliases': ['Stored Water'],
                                     'review_state': 'approved', 'reason': 'Resource alias'}]})
    updated = await bridge.review(preview['glossary_id'], request)
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    row = next(item for item in page['entries'] if item['raw_metadata']['terminology']['concept_id'] == 'mars:water:2')
    assert row['variants']['en'] == ['Stored Water']
    assert row['raw_metadata']['terminology']['human_review']['previous_aliases'] == []
    new_release = await bridge.publish(freeze_request(updated, version='2'))
    assert next(t for t in releases.get(new_release['id'])[1] if t['concept_id'] == 'mars:water:2')['aliases'] == ['Stored Water']
    assert all(not t['aliases'] for t in releases.get(old_release['id'])[1])
    assert await manager.update_entry(row['entry_id'], {'variants': {'en': ['Different Water']},
        'translations': row['translations'], 'metadata': row['raw_metadata'], 'abbreviations': row['abbreviations']})
    current = await bridge.preview(preview['glossary_id'], 'zh-TW')
    assert current['review_states'].get('approved', 0) == 0
    last_release = await bridge.publish(freeze_request(current, version='3'))
    assert next(t for t in releases.get(last_release['id'])[1] if t['concept_id'] == 'mars:water:2')['aliases'] == ['Different Water']


@pytest.mark.asyncio
async def test_reference_cannot_change_aliases(environment):
    bridge, _, _ = environment
    preview = await bridge.import_glossary(import_request())
    request = GlossaryTermReviewRequest.model_validate({'locale': 'zh-TW',
        'expected_fingerprint': preview['fingerprint'], 'review_origin': 'reference', 'approved': True,
        'changes': [{'concept_id': 'mars:water:2', 'aliases': ['Stored Water'], 'review_state': 'candidate'}]})
    with pytest.raises(BatchConflict) as error:
        await bridge.review(preview['glossary_id'], request)
    assert error.value.code == 'reference_cannot_change_decision'
    assert (await bridge.preview(preview['glossary_id'], 'zh-TW'))['fingerprint'] == preview['fingerprint']



@pytest.mark.asyncio
async def test_http_editor_and_agent_routes_share_the_same_glossary(environment):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from scripts.routers import agent_batch, agent_glossary_terminology, glossary

    bridge, _, releases = environment
    app = FastAPI()
    app.include_router(agent_glossary_terminology.router)
    app.include_router(glossary.router)
    app.include_router(agent_batch.router)
    app.dependency_overrides[agent_glossary_terminology.get_terminology_service] = lambda: bridge
    app.dependency_overrides[agent_batch.get_batch_service] = lambda: SimpleNamespace(terms=releases)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/agent/glossaries/terminology', json=import_request().model_dump())
        assert response.status_code == 200
        preview = response.json()
        response = await client.get('/api/glossary/content', params={'glossary_id': preview['glossary_id'], 'pageSize': 100})
        assert response.status_code == 200 and response.json()['totalCount'] == 3
        pending = next(row for row in response.json()['entries'] if row['source'] == 'Idiot')
        response = await client.post(f"/api/agent/glossaries/{preview['glossary_id']}/terminology/review", json={
            'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint'], 'approved': True,
            'changes': [{'concept_id': pending['metadata']['terminology']['concept_id'], 'translation': '愚鈍',
                'sense': 'User-approved trait wording', 'review_state': 'approved', 'reason': 'User decision'}]})
        assert response.status_code == 200
        current = response.json()
        response = await client.post('/api/agent/term-releases/from-glossary', json=freeze_request(current).model_dump())
        assert response.status_code == 200
        release_id = response.json()['id']
        response = await client.get('/api/agent/term-releases/' + release_id)
        assert response.status_code == 200 and response.json()['term_count'] == 3
        chosen = next(term for term in response.json()['terms'] if term['source'] == 'Idiot')
        assert chosen['translation'] == '愚鈍' and chosen['sense'] == 'User-approved trait wording'


@pytest.mark.asyncio
async def test_http_distribution_is_readonly_and_reimportable(environment):
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from scripts.routers import agent_glossary_terminology

    bridge, _, _ = environment
    preview = await bridge.import_glossary(import_request())
    app = FastAPI()
    app.include_router(agent_glossary_terminology.router)
    app.dependency_overrides[agent_glossary_terminology.get_terminology_service] = lambda: bridge
    endpoint = f"/api/agent/glossaries/{preview['glossary_id']}/terminology/distribution"
    params = {'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint']}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        result = await client.get(endpoint, params=params)
        assert result.status_code == 200
        exported = result.json()
        assert exported['snapshot']['eligible_count'] == 2
        assert len(exported['import_payload']['terms']) == 2
        assert await bridge.preview(preview['glossary_id'], 'zh-TW') == preview
        stale = await client.get(endpoint, params={**params, 'expected_fingerprint': 'a' * 64})
        assert stale.status_code == 409 and stale.json()['detail']['code'] == 'glossary_changed'
        invalid = await client.get(endpoint, params={**params, 'locale': 'zh-CN'})
        assert invalid.status_code == 400
    copied = await bridge.import_glossary(TerminologyGlossaryImport.model_validate(
        {**exported['import_payload'], 'approved': True}))
    assert copied['glossary_id'] != preview['glossary_id']
    assert copied['review_states'] == {'reviewed': 1, 'candidate': 1}


@pytest.mark.asyncio
async def test_reference_enrichment_preserves_approval_and_is_visible_to_existing_editor(environment):
    bridge, manager, _ = environment
    preview = await bridge.import_glossary(import_request())
    reference = {'workshop_id': '1749276214', 'source_kind': 'author_public_history', 'source_id': '1',
        'english': 'Water', 'translation': '水資源', 'context': 'Historical quantity label',
        'file_path': 'history/Game.csv', 'file_sha256': 'a' * 64, 'match_status': 'same_id_same_english'}
    request = GlossaryTermReviewRequest.model_validate({'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint'],
        'review_origin': 'reference', 'approved': True, 'changes': [{'concept_id': 'mars:water:1',
            'review_state': 'reviewed', 'historical_reference': reference}]})
    current = await bridge.review(preview['glossary_id'], request)
    assert current['review_states'] == preview['review_states']
    page = await manager.get_glossary_entries_paginated(preview['glossary_id'], 1, 100)
    row = next(row for row in page['entries'] if row['raw_metadata']['terminology']['concept_id'] == 'mars:water:1')
    detail = row['raw_metadata']['terminology']
    assert row['translations']['zh-TW'] == '水量'
    assert detail['historical_reference']['translation'] == '水資源'
    assert 'human_review' not in detail and 'model_review' not in detail
    request.expected_fingerprint = current['fingerprint']
    request.changes[0].translation = 'Changed via reference'
    with pytest.raises(BatchConflict) as invalid:
        await bridge.review(preview['glossary_id'], request)
    assert invalid.value.code == 'reference_cannot_change_decision'


@pytest.mark.asyncio
async def test_optional_history_field_keeps_legacy_import_fingerprint(environment):
    from scripts.core.batch_artifacts import fingerprint
    bridge, manager, _ = environment
    request = import_request()
    legacy = request.model_dump(exclude={'approved'})
    for term in legacy['terms']:
        term.pop('historical_reference')
    preview = await bridge.import_glossary(request)
    glossary = await manager.get_glossary_by_id(preview['glossary_id'])
    assert glossary['raw_metadata']['terminology_import_fingerprint'] == fingerprint(legacy)


@pytest.mark.asyncio
async def test_model_audit_cannot_overwrite_human_decision_or_claim_human_approval(environment):
    bridge, manager, _ = environment
    preview = await bridge.import_glossary(import_request())
    request = GlossaryTermReviewRequest.model_validate({'locale': 'zh-TW', 'expected_fingerprint': preview['fingerprint'],
        'review_origin': 'model', 'reviewer': 'Sol audit', 'approved': True,
        'changes': [{'concept_id': 'mars:water:2', 'review_state': 'approved'}]})
    with pytest.raises(BatchConflict) as invalid:
        await bridge.review(preview['glossary_id'], request)
    assert invalid.value.code == 'model_cannot_human_approve'
    request.review_origin = 'human'
    current = await bridge.review(preview['glossary_id'], request)
    request.review_origin = 'model'
    request.expected_fingerprint = current['fingerprint']
    request.changes[0].review_state = 'reviewed'
    request.changes[0].translation = 'Unwanted model rewrite'
    with pytest.raises(BatchConflict) as protected:
        await bridge.review(preview['glossary_id'], request)
    assert protected.value.code == 'protected_human_decision'
    assert (await bridge.preview(preview['glossary_id'], 'zh-TW'))['fingerprint'] == current['fingerprint']
