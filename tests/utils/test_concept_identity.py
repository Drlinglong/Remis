import pytest

from scripts.utils.game_format_contract import compare_format_structure, parse_format_structure
from scripts.utils.post_process_validator import PostProcessValidator


def errors(source, target, game="victoria3"):
    return [r for r in PostProcessValidator().validate_entry(
        game, "test:0", target, source_value=source, target_lang="custom",
    ) if r.level.value == "error"]


@pytest.mark.parametrize("label", ["ricerca", "研究", r"l\'innovazione", "ricerca, avanzata"])
@pytest.mark.parametrize("game", ["victoria3", "vic3", "ck3"])
def test_label_translation_preserves_runtime_identity(label, game):
    source = "#italic [Concept('concept_research', 'research')|E]#!"
    target = f"#italic [Concept('concept_research', '{label}')|E]#!"
    assert not errors(source, target, game)
    assert not compare_format_structure(source, target, game).hard_issues
    assert parse_format_structure(target, game).runtime_tokens[0].raw in target


@pytest.mark.parametrize("target", [
    "[Concept('other_key', 'ricerca')|E]",
    "[Concept('concept_research', 'ricerca')|L]",
    "[Concept('concept_research', 'ricerca')]",
    "[Concept('concept_research', 'ricerca', 'extra')|E]",
    "[Concept('concept_research', 'ricerca)|E]",
    "[Concept('concept_research', 'ricerca')|E] [Concept('concept_research', 'ricerca')|E]",
    "ricerca",
])
def test_key_modifier_syntax_and_occurrence_changes_still_fail(target):
    assert errors("[Concept('concept_research', 'research')|E]", target)


@pytest.mark.parametrize("source_label,target_label,valid", [
    ("@research! research", "@research! ricerca", True),
    ("@research! research", "@other! ricerca", False),
    ("$VALUE$ research", "$VALUE$ ricerca", True),
    ("$VALUE$ research", "ricerca", False),
    ("[Scope.GetName] research", "[Scope.GetName] ricerca", True),
    ("[Scope.GetName] research", "[Other.GetName] ricerca", False),
    ("#b $VALUE$#! research", "#b $VALUE$#! ricerca", True),
    ("#b $VALUE$#! research", "#b ricerca#! $VALUE$", False),
])
def test_embedded_label_syntax_remains_protected(source_label, target_label, valid):
    source = f"[Concept('concept_research', '{source_label}')]"
    target = f"[Concept('concept_research', '{target_label}')]"
    assert bool(errors(source, target)) is not valid


def test_other_script_arguments_are_not_translatable():
    assert errors("[GetIdeology('ideology_research').GetName]",
                  "[GetIdeology('ideologia_ricerca').GetName]")
    assert errors("[Concept('concept_research', 'research')]",
                  "[Concept('研究', 'ricerca')]")
    assert errors("[concept_research]", "[研究]")


def test_same_label_repetition_reduction_and_format_rebinding_are_not_hidden():
    concept = "[Concept('concept_research', 'research')]"
    translated = "[Concept('concept_research', 'ricerca')]"
    assert errors(f"#b {concept}#!", f"{translated} #b testo#!")
