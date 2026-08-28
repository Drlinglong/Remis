import json
from pathlib import Path

from scripts.core.api_handler import get_handler
from scripts.developer_tools.evaluate_key_context_factorial import (
    ARMS,
    OFFICIAL_LANGUAGE_POLICIES,
    build_arm_prompt,
    build_blind_artifacts,
    build_schedule,
    estimate_schedule_prompt_tokens,
    score_contract_expectations,
    validate_schedule_prompts,
    write_progress_checkpoint,
)
from scripts.developer_tools.evaluate_translation_quality import (
    build_translation_prompt,
    make_task,
)
from scripts.developer_tools.key_context_factorial_fixture import (
    classify_reference_strategy,
    compare_reference_tokens,
    parse_dollar_tokens,
    read_factorial_fixture,
    reference_structural_grade_ceiling,
    resolve_factorial_cases,
)


FIXTURE = Path(__file__).parents[1] / "fixtures/key_context_factorial_smoke_v1.json"


def load_smoke_cases():
    fixture, _ = read_factorial_fixture(FIXTURE)
    return resolve_factorial_cases(fixture, OFFICIAL_LANGUAGE_POLICIES)


def test_core_arms_form_the_requested_two_by_two_prompt_design():
    case = load_smoke_cases()[0]
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, handler.provider_name)
    baseline = build_translation_prompt(case, handler, task)

    prompts = {
        arm_id: build_arm_prompt(case, handler, task, ARMS[arm_id])
        for arm_id in ("A", "B", "C", "D", "E")
    }

    assert prompts["A"] == baseline
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" not in prompts["A"]
    assert "Localization key:" not in prompts["A"]
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" in prompts["B"]
    assert "Localization key:" not in prompts["B"]
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" not in prompts["C"]
    assert 'Localization key: "EGY_ADJ"; Source value: "Egyptian"' in prompts["C"]
    assert '[EGY_ADJ] "Egyptian"' not in prompts["C"]
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" in prompts["D"]
    assert 'Localization key: "EGY_ADJ"; Source value: "Egyptian"' in prompts["D"]
    assert "Semantic hint:" in prompts["E"]
    assert "Localization key:" not in prompts["E"]
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" not in prompts["E"]


def test_f_and_g_are_production_realistic_context_arms():
    case = load_smoke_cases()[0]
    case["detected_semantic_hints"] = {
        "EGY_ADJ:0": (
            "semantic_type=country_adjective_definition; "
            "required_form=reusable_country_entity_stem; "
            "contextual_morphology_owner=use_site"
        )
    }
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, handler.provider_name)

    prompt_f = build_arm_prompt(case, handler, task, ARMS["F"])
    prompt_g = build_arm_prompt(case, handler, task, ARMS["G"])

    assert "relation=possessive" not in prompt_f
    assert 'Localization key: "EGY_ADJ"' not in prompt_f
    assert "semantic_type=country_adjective_definition" in prompt_f
    assert 'Source value: "An Egyptian arrived."' in prompt_f
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" not in prompt_f
    assert 'Localization key: "EGY_ADJ"; Source value: "Egyptian"' in prompt_g
    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" in prompt_g
    assert "Treat every numbered input item as independent" in prompt_f
    assert "Treat every numbered input item as independent" in prompt_g


def test_h_combines_detected_semantics_and_language_policy_without_raw_key():
    case = load_smoke_cases()[0]
    case["detected_semantic_hints"] = {
        "EGY_ADJ:0": (
            "semantic_type=country_adjective_definition; "
            "required_form=reusable_country_entity_stem; "
            "contextual_morphology_owner=use_site"
        )
    }
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, handler.provider_name)

    prompt = build_arm_prompt(case, handler, task, ARMS["H"])

    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" in prompt
    assert "semantic_type=country_adjective_definition" in prompt
    assert 'Localization key: "EGY_ADJ"' not in prompt
    assert "relation=possessive" not in prompt
    assert "Treat every numbered input item as independent" in prompt


def test_h2_uses_language_specific_hint_without_raw_key_or_answer_relation():
    case = load_smoke_cases()[0]
    case["language_specific_semantic_hints"] = {
        "EGY_ADJ:0": (
            "semantic_type=country_adjective_definition; "
            "required_runtime_form=official_reusable_country_entity_form_without_use_site_morphology; "
            "contextual_morphology_owner=use_site"
        )
    }
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, handler.provider_name)

    prompt = build_arm_prompt(case, handler, task, ARMS["H2"])

    assert "TARGET-LANGUAGE MORPHOLOGY POLICY" in prompt
    assert "required_runtime_form=official_reusable_country_entity_form" in prompt
    assert 'Localization key: "EGY_ADJ"' not in prompt
    assert "relation=possessive" not in prompt
    assert "Do not add any formatting marker" in prompt
    assert "original syntactic form" in prompt


def test_official_fixture_adapter_scores_only_definitions_as_exact_gold(tmp_path):
    fixture_path = tmp_path / "cases.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "fixture_id": "vic3-adj-multilingual-v1",
                "game_id": "victoria3",
                "corpus_fingerprint_sha256": "fixture-fingerprint",
                "target_languages": ["simp_chinese"],
                "cases": [
                    {
                        "id": "definition",
                        "key": "EGY_ADJ",
                        "kind": "adj_definition",
                        "focus": "definition",
                        "referenced_adj_tokens": [],
                        "source": {"value": "Egyptian", "source_line": 1},
                        "official_targets": {"simp_chinese": {"value": "埃及"}},
                    },
                    {
                        "id": "reference",
                        "key": "culture",
                        "kind": "adj_reference",
                        "focus": "reference",
                        "referenced_adj_tokens": ["$EGY_ADJ$"],
                        "source": {
                            "value": "$EGY_ADJ$ culture",
                            "source_line": 2,
                        },
                        "official_targets": {
                            "simp_chinese": {"value": "$EGY_ADJ$文化"}
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fixture, _ = read_factorial_fixture(fixture_path)
    cases = resolve_factorial_cases(fixture, OFFICIAL_LANGUAGE_POLICIES)
    assert len(cases) == 2
    case = next(case for case in cases if case["track"] == "adj_definition")

    assert case["target_lang"] == "zh-CN"
    assert [item["key"] for item in case["expectations"]] == ["EGY_ADJ"]
    reference = next(case for case in cases if case["track"] == "adj_reference")
    assert reference["item_metadata"]["culture"]["official_target"] == (
        "$EGY_ADJ$文化"
    )


def test_definition_contract_is_exact_and_controls_can_be_constraint_based():
    case = load_smoke_cases()[0]

    passing = score_contract_expectations(
        case, ["埃及", "他是一名埃及人。", "埃及文化"]
    )
    failing = score_contract_expectations(
        case, ["埃及人", "他是一名埃及人。", "埃及人的文化"]
    )

    assert passing["passed"] is True
    assert failing["passed"] is False
    assert failing["items"][0]["exact_pass"] is False


def test_schedule_is_seeded_and_blind_file_hides_arm_identity():
    cases = load_smoke_cases()[:1]
    arms = [ARMS[arm_id] for arm_id in ("A", "B", "C", "D")]
    first = build_schedule(cases, arms, repetitions=2, seed=207)
    second = build_schedule(cases, arms, repetitions=2, seed=207)
    assert [(arm.arm_id, repetition) for _, arm, repetition in first] == [
        (arm.arm_id, repetition) for _, arm, repetition in second
    ]

    results = [
        {
            "id": cases[0]["id"],
            "repetition": 1,
            "arm_id": arm.arm_id,
            "outputs": [arm.arm_id],
            "score": {"hard_pass": True},
        }
        for arm in arms
    ]
    blind, key = build_blind_artifacts(cases, results, seed=207)

    assert "arm_id" not in json.dumps(blind)
    assert "hard_pass" not in json.dumps(blind)
    assert "EGY_ADJ" not in json.dumps(blind)
    assert {item["arm_id"] for item in key["mapping"]} == {"A", "B", "C", "D"}


def test_local_token_estimate_uses_complete_paired_prompts():
    cases = load_smoke_cases()[:1]
    arms = [ARMS[arm_id] for arm_id in ("A", "B", "C", "D")]
    schedule = build_schedule(cases, arms, repetitions=1, seed=207)
    handler = get_handler("lm_studio", model_name="benchmark-test-model")

    estimate = estimate_schedule_prompt_tokens(schedule, handler)
    cells = {cell["arm_id"]: cell for cell in estimate["cells"]}

    assert estimate["encoding"] == "o200k_base"
    assert cells["A"]["delta_vs_A_tokens"] == 0
    assert cells["B"]["estimated_input_tokens"] > cells["A"]["estimated_input_tokens"]
    assert cells["C"]["estimated_input_tokens"] > cells["A"]["estimated_input_tokens"]
    assert cells["D"]["estimated_input_tokens"] > cells["B"]["estimated_input_tokens"]
    assert estimate["track_cells"][0]["track"] == "mixed"


def test_prompt_compatibility_is_checked_before_model_execution():
    cases = load_smoke_cases()[:1]
    schedule = build_schedule(cases, [ARMS["A"]], repetitions=1, seed=207)
    handler = get_handler("lm_studio", model_name="benchmark-test-model")

    validate_schedule_prompts(schedule, handler)


def test_progress_checkpoint_atomically_preserves_completed_results(tmp_path):
    path = tmp_path / "run_checkpoint.json"

    write_progress_checkpoint(
        path,
        {"status": "in_progress", "completed_run_count": 1, "results": [{"id": 1}]},
    )

    assert json.loads(path.read_text(encoding="utf-8"))["results"] == [{"id": 1}]
    assert not path.with_suffix(".json.tmp").exists()


def test_exact_definition_comparison_preserves_case():
    case = load_smoke_cases()[1]
    result = score_contract_expectations(
        case, ["ägyptisch", "unused", "unused"]
    )

    assert result["passed"] is False


def test_reference_token_parser_separates_modifiers_and_substitutions():
    [modified] = parse_dollar_tokens("$BHT_ADJ|l$ Uprising")
    substitution = compare_reference_tokens("$POR_ADJ$ connection", "$POR$连接")

    assert modified == {
        "raw": "$BHT_ADJ|l$",
        "base_key": "BHT_ADJ",
        "modifiers": ["l"],
    }
    assert substitution["base_key_multiset_preserved"] is False
    assert substitution["token_substitutions"] == [
        {"source_base_key": "POR_ADJ", "target_base_key": "POR"}
    ]
    assert classify_reference_strategy("$POR_ADJ$ connection", "$POR$连接") == (
        "substitute_base_tag"
    )
    assert classify_reference_strategy("$POR_ADJ$ connection", "葡萄牙连接") == (
        "hardcoded"
    )
    assert reference_structural_grade_ceiling(
        "$POR_ADJ$ connection", "葡萄牙连接"
    ) == "PARTIAL"
    assert reference_structural_grade_ceiling(
        "$FIRST_ADJ$-$SECOND_ADJ$ trade", "中法贸易"
    ) == "FAIL"
    assert reference_structural_grade_ceiling(
        "$BHT_ADJ|l$ Uprising", "$BHT_ADJ|l$起义"
    ) == "FULL"
    assert reference_structural_grade_ceiling(
        "$BHT_ADJ$ Uprising", "Soulèvement $BHT_ADJ|l$"
    ) == "FULL"
    assert reference_structural_grade_ceiling(
        "$BHT_ADJ|l$ Uprising", "$BHT_ADJ$起义"
    ) == "PARTIAL"
