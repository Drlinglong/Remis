from pathlib import Path

import pytest

from scripts.core import neologism_manager as neologism_module
from scripts.core.neologism_manager import Candidate, NeologismManager
from scripts.core.neologism_miner import NeologismMiningError, NeologismReview, NeologismTerm


class FakeGlossaryManager:
    def __init__(self):
        self.calls = []

    async def add_entry(self, glossary_id, entry_data):
        self.calls.append((glossary_id, entry_data))
        return True


def make_candidate(**overrides):
    data = {
        "id": "candidate-1",
        "project_id": "project-1",
        "original": "Aetherophasic Engine",
        "context_snippets": ["Aetherophasic Engine powers the crisis."],
        "suggestion": "以太相引擎",
        "reasoning": "Specific Stellaris megastructure.",
        "source_file": "events/test.yml",
        "source_files": ["events/test.yml"],
        "source_lang": "en",
        "target_lang": "zh-CN",
        "frequency": 2,
        "category": "technology",
        "confidence": 0.9,
    }
    data.update(overrides)
    return Candidate(**data)


@pytest.mark.asyncio
async def test_approve_candidate_is_idempotent_and_preserves_languages(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    fake_glossary = FakeGlossaryManager()
    monkeypatch.setattr(neologism_module, "glossary_manager", fake_glossary)

    manager = NeologismManager()
    manager.save_candidates("project-1", [make_candidate()])

    approved = await manager.approve_candidate(
        "project-1",
        "candidate-1",
        "以太相引擎",
        glossary_id=42,
    )
    approved_again = await manager.approve_candidate(
        "project-1",
        "candidate-1",
        "以太相引擎",
        glossary_id=42,
    )

    assert approved is True
    assert approved_again is True
    assert [call[1]["id"] for call in fake_glossary.calls] == ["candidate-1"]
    entry = fake_glossary.calls[0][1]
    assert entry["translations"] == {
        "en": "Aetherophasic Engine",
        "zh-CN": "以太相引擎",
    }
    assert entry["metadata"]["source_text"] == "Aetherophasic Engine"
    assert entry["metadata"]["project_id"] == "project-1"
    assert entry["metadata"]["source_files"] == ["events/test.yml"]
    assert entry["metadata"]["frequency"] == 2
    assert entry["metadata"]["category"] == "technology"
    assert manager.load_candidates("project-1")[0].status == "approved"


@pytest.mark.asyncio
async def test_approve_candidate_preserves_source_when_languages_are_the_same(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    fake_glossary = FakeGlossaryManager()
    monkeypatch.setattr(neologism_module, "glossary_manager", fake_glossary)
    manager = NeologismManager()
    manager.save_candidates(
        "project-1",
        [make_candidate(original="泰尔紫 (Tyrian Purple)", source_lang="zh-CN")],
    )

    approved = await manager.approve_candidate(
        "project-1",
        "candidate-1",
        "泰尔紫",
        glossary_id=42,
        source_lang="zh-CN",
        target_lang="zh-CN",
    )

    assert approved is True
    entry = fake_glossary.calls[0][1]
    assert entry["translations"] == {"zh-CN": "泰尔紫"}
    assert entry["metadata"]["source_text"] == "泰尔紫 (Tyrian Purple)"


@pytest.mark.asyncio
async def test_duplicate_resolution_does_not_write_a_new_glossary_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    fake_glossary = FakeGlossaryManager()
    monkeypatch.setattr(neologism_module, "glossary_manager", fake_glossary)
    manager = NeologismManager()
    manager.save_candidates("project-1", [make_candidate(duplicate_matches=[{"entry_id": "existing"}])])

    approved = await manager.approve_candidate(
        "project-1",
        "candidate-1",
        "",
        glossary_id=None,
        resolution="duplicate",
    )

    assert approved is True
    assert fake_glossary.calls == []
    assert manager.load_candidates("project-1")[0].status == "duplicate"


def test_mining_status_reservation_prevents_parallel_project_runs():
    manager = NeologismManager()

    assert manager.reserve_mining("project-1", "task-1", 3) is True
    assert manager.reserve_mining("project-1", "task-2", 3) is False
    assert manager.get_mining_status("project-1") == {
        "status": "starting",
        "processed_files": 0,
        "total_files": 3,
        "new_terms": 0,
        "duplicate_terms": 0,
        "current_file": None,
        "error": None,
        "task_id": "task-1",
    }


def test_processed_candidates_can_be_restored_without_losing_their_decision_data(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    manager = NeologismManager()
    manager.save_candidates("project-1", [make_candidate(status="ignored")])

    assert manager.get_candidates("project-1", view="pending") == []
    assert manager.get_candidates("project-1", view="processed")[0]["status"] == "ignored"
    assert manager.restore_candidate("project-1", "candidate-1") == "ignored"
    restored = manager.get_candidates("project-1", view="pending")[0]
    assert restored["status"] == "pending"
    assert restored["suggestion"] == "以太相引擎"


def test_candidate_store_rejects_path_like_project_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    manager = NeologismManager()

    with pytest.raises(neologism_module.CandidateStoreError, match="Invalid project_id"):
        manager.load_candidates("../outside")


def test_candidate_store_hashes_project_ids_before_building_cache_paths(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    manager = NeologismManager()

    cache_file = Path(manager._get_cache_file("project-1"))

    assert cache_file.parent == tmp_path
    assert cache_file.name != "project-1.json"
    assert len(cache_file.stem) == 64
    assert set(cache_file.stem) <= set("0123456789abcdef")


class FakeMiner:
    def __init__(self, handler):
        self.handler = handler

    def extract_terms(self, *args, **kwargs):
        return [NeologismTerm(original="Aetherophasic Engine", category="technology", confidence=0.9)]

    def review_terms(self, candidates, **kwargs):
        return {
            candidate["original"]: NeologismReview(
                original=candidate["original"],
                suggestion="以太相引擎",
                reasoning="Specific Stellaris megastructure.",
                confidence=0.9,
            )
            for candidate in candidates
        }


def test_mining_uses_grounded_evidence_and_marks_glossary_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(neologism_module, "get_handler", lambda provider, model_name=None: object())
    monkeypatch.setattr(neologism_module, "NeologismMiner", FakeMiner)

    source_file = tmp_path / "source.yml"
    source_file.write_text(
        'l_english:\n test_key:0 "Aetherophasic Engine powers the crisis."\n',
        encoding="utf-8",
    )

    manager = NeologismManager()
    manager.run_mining_workflow(
        "project-1",
        [str(source_file)],
        "gemini",
        duplicate_index={
            "aetherophasic engine": [
                {
                    "entry_id": "main-entry-1",
                    "glossary_id": 1,
                    "glossary_name": "Main",
                    "source_term": "Aetherophasic Engine",
                    "translations": {"en": "Aetherophasic Engine", "zh-CN": "以太相引擎"},
                }
            ]
        },
    )

    candidates = manager.load_candidates("project-1")
    assert len(candidates) == 1
    assert candidates[0].context_snippets == ["Aetherophasic Engine powers the crisis."]
    assert candidates[0].context_evidence[0].snippet == "Aetherophasic Engine powers the crisis."
    assert candidates[0].context_evidence[0].source_file == str(source_file)
    assert candidates[0].review_language == "en"
    assert candidates[0].frequency == 1
    assert candidates[0].suggestion == "以太相引擎"
    assert candidates[0].duplicate_matches[0]["entry_id"] == "main-entry-1"
    assert manager.get_mining_status("project-1")["duplicate_terms"] == 1


class FailingMiner(FakeMiner):
    def extract_terms(self, *args, **kwargs):
        raise NeologismMiningError("provider returned invalid JSON")


def test_mining_failure_is_terminal_and_does_not_create_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(neologism_module, "get_handler", lambda provider, model_name=None: object())
    monkeypatch.setattr(neologism_module, "NeologismMiner", FailingMiner)
    source_file = tmp_path / "source.yml"
    source_file.write_text('l_english:\n key:0 "The Curia Caelestis rises."\n', encoding="utf-8")
    manager = NeologismManager()

    with pytest.raises(NeologismMiningError, match="invalid JSON"):
        manager.run_mining_workflow("project-1", [str(source_file)], "gemini")

    assert manager.get_mining_status("project-1")["status"] == "failed"
    assert "invalid JSON" in manager.get_mining_status("project-1")["error"]
    assert manager.load_candidates("project-1") == []


class HallucinatingMiner(FakeMiner):
    def extract_terms(self, *args, **kwargs):
        return [NeologismTerm(original="Not Present In Source", confidence=0.9)]


def test_ungrounded_model_terms_are_discarded(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(neologism_module, "get_handler", lambda provider, model_name=None: object())
    monkeypatch.setattr(neologism_module, "NeologismMiner", HallucinatingMiner)
    source_file = tmp_path / "source.yml"
    source_file.write_text('l_english:\n key:0 "The Curia Caelestis rises."\n', encoding="utf-8")
    manager = NeologismManager()

    assert manager.run_mining_workflow("project-1", [str(source_file)], "gemini") == 0
    assert manager.load_candidates("project-1") == []
    assert manager.get_mining_status("project-1")["status"] == "completed"


def test_reject_is_idempotent_but_does_not_overwrite_other_terminal_statuses(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path / "cache"))
    manager = NeologismManager()
    def candidate(candidate_id, status="pending"):
        return Candidate(
            id=candidate_id,
            project_id="project-1",
            original=candidate_id.title(),
            context_snippets=[],
            suggestion="译名",
            reasoning="reason",
            status=status,
        )

    manager.save_candidates("project-1", [
        candidate("pending"),
        candidate("ignored", "ignored"),
        candidate("approved", "approved"),
    ])

    assert manager.reject_candidate("project-1", "pending") == "pending"
    assert manager.reject_candidate("project-1", "ignored") == "ignored"
    assert manager.reject_candidate("project-1", "approved") == "approved"

    statuses = {candidate.id: candidate.status for candidate in manager.load_candidates("project-1")}
    assert statuses == {
        "pending": "ignored",
        "ignored": "ignored",
        "approved": "approved",
    }
