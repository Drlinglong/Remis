from scripts.core.glossary_manager import GlossaryManager


def test_project_glossary_wins_conflicting_source_term():
    manager = GlossaryManager()
    manager.in_memory_glossary = {
        "entries": [
            {
                "entry_id": "main-term",
                "translations": {"en": "Heartfire", "zh-CN": "心火"},
                "variants": {},
                "abbreviations": {},
                "raw_metadata": {},
                "_glossary_priority": 0,
            },
            {
                "entry_id": "project-term",
                "translations": {"en": "Heartfire", "zh-CN": "灵焰"},
                "variants": {},
                "abbreviations": {},
                "raw_metadata": {"kind": "project_neologism_glossary"},
                "_glossary_priority": 2,
            },
        ]
    }

    matches = manager.extract_relevant_terms(["The Heartfire awakens."], "en", "zh-CN")

    assert len(matches) == 1
    assert matches[0]["id"] == "project-term"
    assert matches[0]["translations"]["zh-CN"] == "灵焰"
