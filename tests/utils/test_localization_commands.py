import pytest

from scripts.utils.localization_commands import (
    DICTIONARY_DIR,
    build_command_context,
    find_command_references,
    load_command_dictionary,
    lookup_commands,
    parse_command_chain,
)


@pytest.mark.parametrize("game_id", ["stellaris", "victoria3", "hoi4", "ck3", "eu5"])
def test_every_supported_game_has_a_valid_dictionary(game_id):
    dictionary = load_command_dictionary(game_id)

    assert dictionary["game_id"] == game_id
    assert dictionary["sources"][0]["url"].startswith("https://")
    assert dictionary["commands"]


def test_dictionary_files_are_only_supported_games():
    assert {path.name for path in DICTIONARY_DIR.glob("*.json")} == {
        "stellaris_v1.json", "victoria3_v1.json", "hoi4_v1.json", "ck3_v1.json", "eu5_v1.json",
    }


def test_game_aliases_and_unsupported_games():
    assert load_command_dictionary("vic3")["game_id"] == "victoria3"
    assert load_command_dictionary("eu4") is None
    assert build_command_context(["[Root.GetName]"], "eu4") == ""


def test_parse_chain_handles_saved_scopes_quotes_and_modifiers():
    segments, modifier = parse_command_chain("[SCOPE.sCharacter('ottoman.sultan').GetHerHis|U]")

    assert [(s.name, s.has_args) for s in segments] == [
        ("SCOPE", False), ("sCharacter", True), ("GetHerHis", False),
    ]
    assert modifier == "U"
    assert parse_command_chain("[?global.FNG_LKMT_var|k%]") == ((), "")


def test_only_commands_used_by_the_entry_are_returned():
    text = (
        "Even in [questing_knight_15.GetHerHis] synthetic form, [questing_knight_15.GetSheHe] "
        "[questing_knight_15.GetWasWere] alone. [questing_knight_15.GetSheHe] waited."
    )

    names = [ref.name for ref in find_command_references([text], "stellaris")]

    assert names == ["GetHerHis", "GetSheHe", "GetWasWere"]


def test_suffixes_resolve_to_base_commands():
    stellaris = {ref.name: ref for ref in find_command_references(
        ["[Root.GetSpeciesNamePlural] [This.GetSheHeCap]"], "stellaris")}
    ck3 = {ref.name: ref for ref in find_command_references(
        ["[ROOT.Char.GetFirstNameNicknamedNoTooltipRegnal]"], "ck3")}

    assert (stellaris["GetSpeciesNamePlural"].base, stellaris["GetSpeciesNamePlural"].suffixes) == (
        "GetSpeciesName", ("Plural",))
    assert stellaris["GetSheHeCap"].base == "GetSheHe"
    assert ck3["GetFirstNameNicknamedNoTooltipRegnal"].suffixes == ("Nicknamed", "NoTooltip", "Regnal")


def test_scope_identifiers_are_not_reported_but_unknown_commands_are():
    refs = find_command_references(["[608.Owner.GetName] [ROOT.GetMysteryThing]"], "hoi4")

    assert [(ref.name, ref.kind) for ref in refs] == [("GetName", "command"), ("GetMysteryThing", "unknown")]


def test_concept_links_are_detected():
    vic3 = find_command_references(["[concept_interest_group]"], "victoria3")
    ck3 = find_command_references(["[legitimacy|e]"], "ck3")

    assert [ref.kind for ref in vic3] == ["concept"]
    assert [ref.kind for ref in ck3] == ["concept"]


def test_context_includes_language_notes_only_for_matching_target():
    text = "[questing_knight_1.GetHerHis] honor"

    zh = build_command_context([text], "stellaris", "zh-CN")
    de = build_command_context([text], "stellaris", "de")

    assert "GetHerHis: pronoun her or his by gender" in zh
    assert "可作主语" in zh
    assert "可作主语" not in de
    assert "GetStarName" not in zh
    assert build_command_context(["No commands here."], "stellaris", "zh-CN") == ""


def test_context_marks_inferred_meanings():
    context = build_command_context(["[Root.GetHisHer]"], "stellaris")

    assert "GetHisHer: pronoun his or her by gender" in context
    assert "(meaning inferred from the name)" in context


def test_lookup_for_agent_tools():
    found, missing = lookup_commands("hoi4", ["GetNameDefCap", "GetNothing"])

    assert found["base"] == "GetNameDef" and found["suffixes"] == ["Cap"]
    assert found["source"] == "https://hoi4.paradoxwikis.com/Localisation"
    assert missing == {"name": "GetNothing", "found": False}
