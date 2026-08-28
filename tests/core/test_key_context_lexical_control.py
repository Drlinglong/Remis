from pathlib import Path

from scripts.core.api_handler import get_handler
from scripts.developer_tools.evaluate_key_context_factorial import (
    ARMS,
    OFFICIAL_LANGUAGE_POLICIES,
    build_arm_prompt,
)
from scripts.developer_tools.evaluate_translation_quality import make_task
from scripts.developer_tools.key_context_factorial_fixture import (
    read_factorial_fixture,
    resolve_factorial_cases,
)
from scripts.developer_tools.key_context_lexical_control import (
    attach_lexical_control,
    load_lexical_control,
)


ROOT = Path(__file__).parents[2]
CONTROL = ROOT / "tests/fixtures/vic3_adj_composition_zh_cn_v1/cases.json"
OFFICIAL = ROOT / "tests/fixtures/vic3_adj_multilingual_v1/cases.json"


def test_shared_lexical_control_is_identical_and_visible_to_every_arm():
    fixture, _ = read_factorial_fixture(OFFICIAL)
    cases = resolve_factorial_cases(
        fixture,
        OFFICIAL_LANGUAGE_POLICIES,
        {"vic3_adj_simp_chinese_definitions"},
    )
    entries, _ = load_lexical_control(CONTROL)
    [case] = attach_lexical_control(cases, entries)
    handler = get_handler("lm_studio", model_name="benchmark-test-model")
    task = make_task(case, handler.provider_name)

    prompts = {
        arm_id: build_arm_prompt(case, handler, task, ARMS[arm_id])
        for arm_id in ("A", "B", "C", "D", "E")
    }

    assert all("'American' → '美利坚'" in prompt for prompt in prompts.values())
    assert all("'British' → '不列颠'" in prompt for prompt in prompts.values())
    assert len({prompt.count("'American' → '美利坚'") for prompt in prompts.values()}) == 1
