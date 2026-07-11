import pytest

from scripts.core import neologism_manager as neologism_module
from scripts.core.neologism_manager import Candidate, NeologismManager


class FakeGlossaryManager:
    def __init__(self):
        self.calls = []

    async def add_entry(self, glossary_id, entry_data):
        self.calls.append((glossary_id, entry_data))
        return True


@pytest.mark.asyncio
async def test_approve_candidate_awaits_glossary_write_and_preserves_languages(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    fake_glossary = FakeGlossaryManager()
    monkeypatch.setattr(neologism_module, "glossary_manager", fake_glossary)

    manager = NeologismManager()
    manager.save_candidates("project-1", [
        Candidate(
            id="candidate-1",
            project_id="project-1",
            original="Aetherophasic Engine",
            context_snippets=["Aetherophasic Engine powers the crisis."],
            suggestion="以太相引擎",
            reasoning="Specific Stellaris megastructure.",
            source_file="events/test.yml",
            source_lang="en",
            target_lang="zh-CN",
        )
    ])

    approved = await manager.approve_candidate(
        "project-1",
        "candidate-1",
        "以太相引擎",
        glossary_id=42,
    )

    assert approved is True
    assert fake_glossary.calls == [
        (
            42,
            {
                "id": fake_glossary.calls[0][1]["id"],
                "translations": {
                    "en": "Aetherophasic Engine",
                    "zh-CN": "以太相引擎",
                },
                "metadata": {
                    "remarks": "Auto-mined. Reasoning: Specific Stellaris megastructure.",
                    "source_file": "events/test.yml",
                    "source_lang": "en",
                    "target_lang": "zh-CN",
                },
                "variants": {},
                "abbreviations": {},
            },
        )
    ]
    assert manager.load_candidates("project-1")[0].status == "approved"


def test_mining_status_defaults_and_updates():
    manager = NeologismManager()

    assert manager.get_mining_status("project-1")["status"] == "idle"

    manager._set_mining_status("project-1", status="running", processed_files=1, total_files=3)

    assert manager.get_mining_status("project-1") == {
        "status": "running",
        "processed_files": 1,
        "total_files": 3,
        "new_terms": 0,
        "current_file": None,
        "error": None,
    }


class FakeExtractedTerm:
    original = "Aetherophasic Engine"
    suggestion = "以太相引擎"
    reasoning = "Specific Stellaris megastructure."


class FakeMiner:
    def __init__(self, handler):
        self.handler = handler

    def extract_terms(self, *args, **kwargs):
        return [FakeExtractedTerm()]


def test_mining_marks_candidates_that_duplicate_main_glossary_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(neologism_module, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(neologism_module, "get_handler", lambda provider: object())
    monkeypatch.setattr(neologism_module, "NeologismMiner", FakeMiner)

    source_file = tmp_path / "source.yml"
    source_file.write_text("Aetherophasic Engine powers the crisis.", encoding="utf-8")

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
                }
            ]
        },
    )

    candidates = manager.load_candidates("project-1")
    assert len(candidates) == 1
    assert candidates[0].duplicate_matches == [
        {
            "entry_id": "main-entry-1",
            "glossary_id": 1,
            "glossary_name": "Main",
            "source_term": "Aetherophasic Engine",
        }
    ]
    assert manager.get_mining_status("project-1")["duplicate_terms"] == 1
