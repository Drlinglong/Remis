import pytest

from scripts.utils.game_format_contract import compare_format_structure
from scripts.utils.post_process_validator import PostProcessValidator


@pytest.mark.parametrize(
    ("game_id", "source", "target"),
    [
        ("vic3", "#BOLD Important#!", "#BOLD 重要#!"),
        ("ck3", "#P Prestige#!", "#P 威望#!"),
        ("hoi4", "§YImportant§!", "§Y重要§!"),
        ("stellaris", "§G+10%§! yield", "§G+10%§! 产出"),
    ],
)
def test_exact_format_identity_is_preserved(game_id, source, target):
    diff = compare_format_structure(source, target, game_id)

    assert diff.passed
    assert not diff.hard_issues


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("#italic Text#!", "#b 文本#!"),
        ("#BOLD Text#!", "#bold 文本#!"),
        ("#blue Text#!", "#b lue 文本#!"),
    ],
)
def test_vic3_format_identity_mismatch_is_not_count_only_pass(source, target):
    diff = compare_format_structure(source, target, "victoria3")

    assert "format_tag_identity" in diff.hard_issues
    assert not diff.passed


def test_vic3_protected_token_modifier_is_exact():
    diff = compare_format_structure(
        "Gain $ENERGY|Y$ [Root.GetName]",
        "获得 $ENERGY$ [Root.GetName]",
        "vic3",
    )

    assert "protected_token_identity" in diff.hard_issues
    assert diff.protected_identity_changes[0]["source"] == "$ENERGY|Y$"
    assert diff.protected_identity_changes[0]["target"] == "$ENERGY$"


def test_ck3_concept_label_can_translate_without_changing_identity():
    diff = compare_format_structure(
        "Respect [Concept('faith', 'religion')|E].",
        "尊重 [Concept('faith', '宗教')|E]。",
        "ck3",
    )

    assert diff.passed


def test_format_boundary_rebinding_is_blocked():
    diff = compare_format_structure(
        "#v $A$#! $B$",
        "#v $B$#! $A$",
        "vic3",
    )

    assert "protected_token_order" in diff.hard_issues
    assert "format_boundary" in diff.hard_issues


def test_source_imbalance_is_separate_from_target_repair():
    diff = compare_format_structure("#bold Text", "#bold 文本#!", "vic3")

    assert diff.source_issue
    assert not diff.hard_issues
    assert not diff.repairable
    assert diff.reviewable


def test_unclosed_pound_icon_is_a_structure_error():
    diff = compare_format_structure("Gain £energy£", "获得 £energy", "stellaris")

    assert diff.target.balanced is False
    assert "target_unbalanced" in diff.hard_issues


def test_source_and_target_anomalies_are_both_reported_without_repair_queue():
    validator = PostProcessValidator()
    results = validator.validate_entry(
        "stellaris",
        "demo_key",
        "获得 £energy",
        source_value="Gain £energy",
    )

    codes = {result.code: result for result in results}
    assert "validation_source_format_unbalanced" in codes
    assert "validation_format_structure_mismatch" in codes
    assert codes["validation_format_structure_mismatch"].details_params["repairQueue"] is False


def test_known_format_count_delta_is_reviewable_not_automatically_repaired():
    diff = compare_format_structure(
        "#bold First#! and #bold Second#!",
        "#bold 合并后的文字#!",
        "vic3",
    )

    assert not diff.hard_issues
    assert diff.possible_variations
    assert diff.reviewable
    assert not diff.repairable


def test_escaped_line_break_reflow_is_not_a_runtime_token_mismatch():
    diff = compare_format_structure(
        "First\\n\\n#bold [Root.GetName]#!\\n\\nSecond",
        "First\\n\\n#bold [Root.GetName]#! translated\\n\\nSecond",
        "vic3",
    )

    assert all(token.raw != "\\n" for token in diff.source.runtime_tokens)
    assert all(token.raw != "\\n" for token in diff.target.runtime_tokens)
    assert "protected_token_parity" not in diff.hard_issues
    assert "protected_token_order" not in diff.hard_issues


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (
            "#blue [CHARACTER.GetFullName] asked [CHARACTER.GetFullName] to join.#!",
            "#blue [CHARACTER.GetFullName] joined.#!",
        ),
        (
            "[TARGET_COUNTRY.GetName] told [TARGET_COUNTRY.GetName] it would recover.",
            "[TARGET_COUNTRY.GetName] announced recovery.",
        ),
    ],
)
def test_duplicate_runtime_token_reduction_is_reviewable_not_hard_corruption(source, target):
    diff = compare_format_structure(source, target, "vic3")

    assert diff.runtime_variation_only
    assert diff.possible_variations
    assert not diff.hard_issues
    assert diff.reviewable
    assert not diff.repairable


def test_validator_does_not_requeue_duplicate_runtime_token_reduction():
    validator = PostProcessValidator()
    results = validator.validate_entry(
        "victoria3",
        "reasonable_merge",
        "#blue [CHARACTER.GetFullName] joined.#!",
        source_value="#blue [CHARACTER.GetFullName] asked [CHARACTER.GetFullName] to join.#!",
        target_lang="zh-CN",
    )

    variation_results = [
        result
        for result in results
        if result.code == "validation_format_structure_variation"
    ]
    assert variation_results
    assert variation_results[0].details_params["classification"] == "possible_reasonable_variation"
    assert not [
        result
        for result in results
        if result.code == "validation_vic3_variable_parity_mismatch"
    ]


def test_validator_emits_structured_identity_gate_for_all_supported_families():
    validator = PostProcessValidator()
    cases = [
        ("vic3", "#italic Text#!", "#b 文本#!"),
        ("ck3", "#P Text#!", "#B 文本#!"),
        ("hoi4", "§YText§!", "§R文本§!"),
        ("stellaris", "§YText§!", "§R文本§!"),
        ("eu5", "#P Text#!", "#B 文本#!"),
    ]

    for game_id, source, target in cases:
        results = validator.validate_entry(game_id, "demo_key", target, source_value=source)
        identity_results = [
            result
            for result in results
            if result.code == "validation_format_tag_identity_mismatch"
        ]
        assert identity_results, game_id
        assert identity_results[0].level.value == "error"
        assert identity_results[0].details_params["blocking"] is True


def test_validator_marks_source_format_anomaly_for_review():
    validator = PostProcessValidator()

    results = validator.validate_entry(
        "victoria3",
        "demo_key",
        "#bold 文本#!",
        source_value="#bold Text",
    )

    source_results = [
        result
        for result in results
        if result.code == "validation_source_format_unbalanced"
    ]
    assert source_results
    assert source_results[0].details_params["classification"] == "source_defect"
    assert source_results[0].details_params["repairQueue"] is False


@pytest.mark.parametrize(
    ("game_id", "source", "target"),
    [
        ("hoi4", "Cost [?cost|R] @GER £army_xp£ §YText§!", "消耗 [?cost|G] @GER £army_xp£ §Y文本§!"),
        ("stellaris", "Gain $ENERGY|Y$ £energy£ §YText§!", "获得 $ENERGY$ £energy£ §Y文本§!"),
        ("ck3", "[GetTrait('brave').GetName(C.Self)]", "[GetTrait('kind').GetName(C.Self)]"),
    ],
)
def test_game_specific_runtime_identity_is_not_count_only(game_id, source, target):
    diff = compare_format_structure(source, target, game_id)

    assert diff.hard_issues
    assert "protected_token_identity" in diff.hard_issues


def test_cross_game_marker_families_are_rejected():
    stellaris_diff = compare_format_structure("§YText§!", "#P Text#!", "stellaris")
    vic3_diff = compare_format_structure("#P Text#!", "§YText§!", "vic3")

    assert "format_tag_identity" in stellaris_diff.hard_issues
    assert "format_tag_identity" in vic3_diff.hard_issues


def test_eu5_uses_the_same_hash_contract_as_its_validator_profile():
    diff = compare_format_structure("#BOLD Important#! @gold!", "#bold 重要#! @gold!", "eu5")

    assert "format_tag_identity" in diff.hard_issues
