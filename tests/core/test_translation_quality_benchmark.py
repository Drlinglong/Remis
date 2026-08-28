import json
import logging
import sys
from pathlib import Path

from scripts.app_settings import PROJECT_ROOT, config_manager
from scripts.core.hunyuan_handler import HunyuanHandler
from scripts.core.prompt_manager import prompt_manager
from scripts.developer_tools.evaluate_translation_quality import (
    DEFAULT_FIXTURE,
    build_translation_prompt,
    discover_single_model,
    extract_protected_tokens,
    make_task,
    main,
    read_fixture,
    resolve_case,
    run_repair_case,
    run_translation_case,
    score_outputs,
    summarize_results,
    token_parity,
    validate_fixture,
)
from scripts.core.api_handler import get_handler
from scripts.core.glossary_manager import glossary_manager
from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.utils.post_process_validator import PostProcessValidator


class FakeHandler:
    provider_name = "lm_studio"

    def __init__(self, outputs):
        self.outputs = outputs
        self.client = object()

    def _build_prompt(self, task):
        return f"benchmark prompt for {len(task.texts)} item(s)"

    def _call_api(self, client, prompt):
        return "fake raw response"

    def _parse_response(self, response, original_texts, target_lang_code):
        return self.outputs


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def load_fixture():
    fixture, _ = read_fixture(DEFAULT_FIXTURE)
    return fixture


def test_fixture_resolves_all_frozen_files_and_keys():
    fixture = load_fixture()

    resolved = validate_fixture(fixture)

    assert len(resolved) == 7
    assert all(case["source_path"].is_file() for case in resolved)
    assert {case["game_id"] for case in resolved} == {"stellaris", "victoria3"}


def test_stellaris_archive_uses_keys_from_requested_local_demo_when_present():
    local_file = Path(PROJECT_ROOT) / (
        "source_mod/Test_Project_Remis_stellaris/localisation/english/"
        "remis_demo_events_l_english.yml"
    )
    archive_file = Path(PROJECT_ROOT) / "archive/remis_demo_events_l_english.yml"

    if local_file.exists():
        local_keys = {key for key, _, _ in parse_loc_file_with_lines(local_file)}
        archive_keys = {key for key, _, _ in parse_loc_file_with_lines(archive_file)}
        fixture_keys = {
            key
            for case in load_fixture()["translation_cases"]
            if case["game_id"] == "stellaris"
            for key in case["keys"]
        }
        assert fixture_keys <= local_keys
        assert fixture_keys <= archive_keys


def test_protected_token_parity_reports_missing_and_extra_markers():
    source = "§Y[Root.GetName]§! has $VALUE$\\nready"
    target = "[Root.GetName] has $OTHER$ ready"

    result = token_parity(source, target)

    assert result["passed"] is False
    assert set(result["missing"]) == {"§Y", "§!", "$VALUE$", "\\n"}
    assert result["extra"] == ["$OTHER$"]
    assert extract_protected_tokens(source)["[Root.GetName]"] == 1


def test_lm_studio_auto_discovery_uses_loaded_instance(monkeypatch):
    handler = type(
        "DiscoveryHandler",
        (),
        {"provider_name": "lm_studio", "base_url": "http://localhost:1234/v1"},
    )()
    payload = {
        "models": [
            {"key": "installed-only", "loaded_instances": []},
            {
                "key": "google/gemma-4-31b-qat",
                "loaded_instances": [{"id": "google/gemma-4-31b-qat"}],
            },
        ]
    }
    monkeypatch.setattr(
        "scripts.developer_tools.evaluate_translation_quality.requests.get",
        lambda url, timeout: FakeResponse(payload),
    )

    assert discover_single_model(handler) == "google/gemma-4-31b-qat"


def test_repair_references_satisfy_hard_constraints_and_broken_inputs_do_not():
    fixture = load_fixture()
    validator = PostProcessValidator()

    for raw_case in fixture["repair_cases"]:
        case = resolve_case(raw_case)
        clean = score_outputs(case, case["clean_translation"], validator)
        broken = score_outputs(case, case["broken_translation"], validator)

        assert clean["hard_pass"] is True, raw_case["id"]
        assert broken["hard_pass"] is False, raw_case["id"]


def test_first_pass_format_failure_is_measurement_not_execution_failure():
    raw_case = load_fixture()["translation_cases"][0]
    case = resolve_case(raw_case)
    output_without_required_tokens = ["这是一段流畅但破坏了全部格式标记的译文。"]

    result = run_translation_case(
        case,
        FakeHandler(output_without_required_tokens),
        PostProcessValidator(),
    )

    assert result["execution_failure"] is None
    assert result["score"]["hard_pass"] is False
    assert result["score"]["protected_token_pass_rate"] == 0.0


def test_contextual_glossary_case_uses_production_injection_and_restores_state():
    raw_case = next(
        case
        for case in load_fixture()["translation_cases"]
        if case["id"] == "victoria3_contextual_glossary"
    )
    case = resolve_case(raw_case)
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, "lm_studio")
    original = glossary_manager.in_memory_glossary
    previous = {"entries": [{"entry_id": "sentinel"}]}
    glossary_manager.in_memory_glossary = previous

    try:
        prompt = build_translation_prompt(case, handler, task)

        assert "'France' → '法兰西'" in prompt
        assert "'Texas' → '得克萨斯'" in prompt
        assert "'silo' → '发射井'" in prompt
        assert "'prestige goods' → '名贵商品'" in prompt
        assert "仅用于军事领域" in prompt
        assert "不应拆分或译为‘威望良好’" in prompt
        assert "Remarks define when a glossary translation applies" in prompt
        assert "only when the source context matches those Remarks" in prompt
        assert "must be translated strictly according to the glossary" not in prompt
        assert glossary_manager.in_memory_glossary is previous
    finally:
        glossary_manager.in_memory_glossary = original


def test_custom_global_prompt_reaches_production_prompt_without_replacing_task_context(
    monkeypatch,
):
    raw_case = load_fixture()["translation_cases"][0]
    case = resolve_case(raw_case)
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, "lm_studio")
    task.file_task.mod_context = "ISSUE_161_TASK_CONTEXT"
    stored_settings = {}
    monkeypatch.setattr(
        config_manager,
        "get_value",
        lambda key, default=None: stored_settings.get(key, default),
    )
    monkeypatch.setattr(
        config_manager,
        "set_value",
        lambda key, value: stored_settings.__setitem__(key, value),
    )
    prompt_manager.save_custom_global_prompt("ISSUE_161_GLOBAL_PROMPT")

    prompt = handler._build_prompt(task)

    assert "ISSUE_161_TASK_CONTEXT" in prompt
    assert "ISSUE_161_GLOBAL_PROMPT" in prompt

    task.file_task.mod_context = "ISSUE_161_GLOBAL_PROMPT"
    deduplicated_prompt = handler._build_prompt(task)

    assert deduplicated_prompt.count("ISSUE_161_GLOBAL_PROMPT") == 1


def test_hunyuan_prompt_keeps_context_global_prompt_and_contextual_glossary(
    monkeypatch,
):
    raw_case = next(
        case
        for case in load_fixture()["translation_cases"]
        if case["id"] == "victoria3_contextual_glossary"
    )
    case = resolve_case(raw_case)
    task = make_task(case, "hunyuan")
    task.file_task.mod_context = "ISSUE_161_HUNYUAN_CONTEXT"
    handler = object.__new__(HunyuanHandler)
    handler.provider_name = "hunyuan"
    handler.model_id = "issue-161-test-model"
    handler.logger = logging.getLogger("issue-161-hunyuan-test")
    monkeypatch.setattr(
        prompt_manager,
        "get_custom_global_prompt",
        lambda: "ISSUE_161_HUNYUAN_GLOBAL_PROMPT",
    )

    prompt = build_translation_prompt(case, handler, task)

    assert "ISSUE_161_HUNYUAN_CONTEXT" in prompt
    assert "ISSUE_161_HUNYUAN_GLOBAL_PROMPT" in prompt
    assert "'silo' → '发射井'" in prompt
    assert "only when the source context matches those Remarks" in prompt


def test_hunyuan_prompt_treats_semantic_hint_as_metadata(monkeypatch):
    raw_case = next(
        case
        for case in load_fixture()["translation_cases"]
        if case["game_id"] == "victoria3"
    )
    case = resolve_case(raw_case)
    task = make_task(case, "hunyuan")
    task.texts = ["Chinese"]
    task.start_index = 0
    task.end_index = 1
    task.file_task.target_lang = {"code": "zh-CN", "name": "简体中文"}
    task.file_task.semantic_hints = [
        "country_adjective_definition: render the country form"
    ]
    handler = object.__new__(HunyuanHandler)
    handler.provider_name = "hunyuan"
    handler.model_id = "semantic-hint-test-model"
    handler.logger = logging.getLogger("semantic-hint-hunyuan-test")
    monkeypatch.setattr(
        prompt_manager,
        "get_custom_global_prompt",
        lambda: "",
    )

    prompt = handler._build_prompt(task)

    assert 'Source value: "Chinese"' in prompt
    assert "the Semantic hint is context, not source text" in prompt
    assert "Do not translate or echo the metadata" in prompt
    assert "Preserve one output line per input line" in prompt


def test_contextual_glossary_scoring_rewards_following_and_disambiguation():
    raw_case = next(
        case
        for case in load_fixture()["translation_cases"]
        if case["id"] == "victoria3_contextual_glossary"
    )
    case = resolve_case(raw_case)
    validator = PostProcessValidator()
    correct = [
        "我们来到#Y 法兰西#!乡间，看见装满麦子的筒仓。\\n\\n蕾姆丝说，法兰西农业公司的名贵商品果然名不虚传。\\n\\n假期十分愉快。\\n\\n下一站是#Y 得克萨斯#!。",
        "检查人员确认，这是一座用于储存并发射洲际弹道导弹的#R 发射井#!。",
    ]
    mechanical = [
        "我们来到#Y 法国#!乡间，看见装满麦子的发射井。\\n\\n蕾姆丝说，法国农业公司的威望良好果然名不虚传。\\n\\n假期十分愉快。\\n\\n下一站是#Y 德克萨斯#!。",
        "检查人员确认，这是一座用于储存并发射洲际弹道导弹的#R 发射井#!。",
    ]

    correct_score = score_outputs(case, correct, validator)
    mechanical_score = score_outputs(case, mechanical, validator)

    assert correct_score["glossary"]["passed"] is True
    assert correct_score["quality_constraint_pass"] is True
    assert mechanical_score["hard_pass"] is True
    assert mechanical_score["glossary"]["passed"] is False
    assert mechanical_score["quality_constraint_pass"] is False


def test_repair_track_scores_final_output_and_preserves_valid_items():
    raw_case = load_fixture()["repair_cases"][0]
    case = resolve_case(raw_case)

    result = run_repair_case(
        case,
        FakeHandler(case["clean_translation"]),
        PostProcessValidator(),
    )

    assert result["execution_failure"] is None
    assert result["score"]["hard_pass"] is True
    assert result["score"]["valid_items_unchanged"] is True
    assert result["score"]["reference_exact_match"] is True


def test_summary_separates_api_failures_from_structured_output_failures():
    results = [
        {
            "execution_failure": None,
            "elapsed_seconds": 1.25,
            "score": {
                "parsed": False,
                "item_count_match": False,
                "hard_pass": False,
                "quality_constraint_pass": False,
            },
        },
        {
            "execution_failure": "ConnectionError: offline",
            "elapsed_seconds": None,
            "score": {
                "parsed": False,
                "item_count_match": False,
                "hard_pass": False,
                "quality_constraint_pass": False,
            },
        },
    ]

    summary = summarize_results(results)

    assert summary["execution_failure_count"] == 1
    assert summary["structured_output_failure_count"] == 2
    assert summary["elapsed_seconds"] == 1.25


def test_dry_run_filters_cases_without_initializing_model_or_writing_results(
    monkeypatch, capsys, tmp_path
):
    fixture = load_fixture()
    repair_case = next(
        case
        for case in fixture["repair_cases"]
        if case["id"] == "stellaris_missing_color_tags"
    )
    output_dir = tmp_path / "benchmark-results"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_translation_quality.py",
            "--dry-run",
            "--track",
            "repair",
            "--case",
            "stellaris_missing_color_tags",
            "--output-dir",
            str(output_dir),
        ],
    )
    monkeypatch.setattr(
        "scripts.developer_tools.evaluate_translation_quality.get_handler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not initialize a model handler")
        ),
    )

    assert main() == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["case_count"] == 1
    assert plan["cases"] == [
        {
            "id": repair_case["id"],
            "track": "repair",
            "game_id": repair_case["game_id"],
            "direction": (
                f"{repair_case['source_lang']} -> {repair_case['target_lang']}"
            ),
            "source_file": repair_case["source_file"],
            "keys": repair_case["keys"],
        }
    ]
    assert not output_dir.exists()
