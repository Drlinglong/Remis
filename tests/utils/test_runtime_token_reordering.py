"""Issue #234: word order must not send intact runtime tokens to repair."""

import pytest

from scripts.utils.game_format_contract import compare_format_structure
from scripts.utils.format_structure_validator import structure_findings
from scripts.utils.post_process_validator import PostProcessValidator


# The issue's ten diagnostics are two findings for each of these five pairs.
ISSUE_234_CASES = [
    (
        "A bonus or penalty to the [concept_sol] of employees in $bg_arts$",
        "对 $bg_arts$ 中雇员的 [concept_sol] 的加成或惩罚",
    ),
    (
        "[concept_infrastructure_usage] of $bg_heavy_industry$ buildings",
        "$bg_heavy_industry$ 建筑的 [concept_infrastructure_usage]",
    ),
    (
        "A bonus or penalty to the [concept_infrastructure_usage] of $bg_heavy_industry$ buildings",
        "对 $bg_heavy_industry$ 建筑的 [concept_infrastructure_usage] 的加成或惩罚",
    ),
    (
        "An increase or decrease to the weekly [concept_construction] progress for $bg_high_tech$ buildings",
        "对 $bg_high_tech$ 建筑每周 [concept_construction] 进度的增加或减少",
    ),
    (
        "A bonus or penalty to the [concept_sol] of [Concept('concept_pop', '$concept_pops$')] "
        "working in $bg_military$ buildings",
        "对在 $bg_military$ 建筑中工作的 [Concept('concept_pop', '$concept_pops$')] "
        "的 [concept_sol] 的加成或惩罚",
    ),
]


def _blocking_findings(game_id, source, target):
    return [
        result for result in PostProcessValidator().validate_entry(
            game_id, "runtime_reorder", target, source_value=source, target_lang="zh-CN",
        ) if result.level.value == "error"
    ]


@pytest.mark.parametrize(("source", "target"), ISSUE_234_CASES)
def test_issue_234_pairs_pass_structure_and_do_not_enter_repair(source, target):
    diff = compare_format_structure(source, target, "victoria3")

    assert diff.passed
    assert not diff.missing_protected
    assert not diff.extra_protected
    assert not diff.protected_identity_changes
    assert not diff.protected_order_changed
    assert not diff.repairable
    assert not _blocking_findings("victoria3", source, target)


@pytest.mark.parametrize(("game_id", "source", "target"), [
    ("vic3", "$A|Y$ [Root.GetName] @gold!", "@gold! [Root.GetName] $A|Y$"),
    ("ck3", "[Root.GetName] $A$", "$A$ [Root.GetName]"),
    ("hoi4", "[?cost|R] @GER £army_xp£", "£army_xp£ @GER [?cost|R]"),
    ("stellaris", "$ENERGY|Y$ £energy£", "£energy£ $ENERGY|Y$"),
    ("eu5", "[Root.GetName] @gold!", "@gold! [Root.GetName]"),
    ("vic3", "#v $A$#! #bold $B$#!", "#bold $B$#! #v $A$#!"),
    ("vic3", "$A$ #bold $C$#! $B$", "$B$ #bold $C$#! $A$"),
    ("vic3", "$A$ $A$ $B$", "$B$ $A$ $A$"),
])
def test_reordering_keeps_runtime_identities_counts_and_span_bindings(game_id, source, target):
    diff = compare_format_structure(source, target, game_id)

    assert diff.passed
    assert not _blocking_findings(game_id, source, target)


@pytest.mark.parametrize(("source", "target", "expected"), [
    ("[concept_sol] $A$", "$A$", "protected_token_parity"),
    ("[concept_sol] $A$", "$A$ [concept_sol] $A$", "protected_token_parity"),
    ("[concept_sol] $A|Y$", "$A$ [concept_sol]", "protected_token_parity"),
    ("[concept_sol] $A$", "$B$ [concept_sol]", "protected_token_parity"),
    ("[concept_sol] $A$", "$A$ [concept_SOL]", "protected_token_parity"),
    (
        "[concept_sol] [Concept('concept_pop', '$concept_pops$')] $A$",
        "$A$ [Concept('concept_pop', '$other$')] [concept_sol]",
        "protected_token_parity",
    ),
    ("#v $A$#! $B$", "#v $B$#! $A$", "format_boundary"),
    ("#v $A$#! #v $B$#!", "#v $B$ $A$#! #v text#!", "format_boundary"),
    ("#v $A$ $B$#!", "#v $B$ $A$#!", "format_boundary"),
    ("#v $A$#! $B$", "$B$ #bold $A$#!", "format_tag_identity"),
    ("#v $A$#! $B$", "$B$ #v $A$", "target_unbalanced"),
    ("#v $A$#! $B$", "$B$ #v $A$#!#!", "target_unbalanced"),
    ("#v $A$#! #bold $B$#!", "#v $A$ #bold $B$#!#!", "format_tag_order"),
])
def test_reordering_does_not_hide_runtime_or_format_corruption(source, target, expected):
    diff = compare_format_structure(source, target, "vic3")

    assert expected in diff.hard_issues
    assert not diff.passed
    assert diff.repairable
    assert _blocking_findings("vic3", source, target)
    assert any(finding["blocking"] and finding["repair_queue"] for finding in structure_findings(diff))
