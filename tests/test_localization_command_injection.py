from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.core.agents.fix_agent import ReflexionFixAgent
from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.copilot import help_agent
from scripts.core.copilot.help_agent import HelpAnswer, HelpDeps
from scripts.core.parallel_types import BatchTask, FileTask

PRONOUN_SOURCE = "Even in [questing_knight_15.GetHerHis] synthetic form, [questing_knight_15.GetSheHe] waited."
REFERENCE_HEADER = "LOCALIZATION COMMAND REFERENCE"


def _batch_task(texts, game_id="stellaris", target_code="zh-CN"):
    file_task = MagicMock(spec=FileTask)
    file_task.target_lang = {"name": "Simplified Chinese", "code": target_code}
    file_task.game_profile = {"id": game_id}
    task = MagicMock(spec=BatchTask)
    task.file_task = file_task
    task.texts = texts
    task.start_index = 0
    return task


def test_translation_fixer_prompt_includes_only_used_commands():
    task = _batch_task([PRONOUN_SOURCE])
    prompt = TranslationFixerAgent(MagicMock())._build_fix_prompt(task, ["bad"], {1: []})

    assert REFERENCE_HEADER in prompt
    assert "GetHerHis: pronoun her or his by gender" in prompt
    assert "可作主语" in prompt
    assert "GetStarName" not in prompt


def test_translation_fixer_prompt_has_no_reference_without_commands():
    task = _batch_task(["Plain text."])
    prompt = TranslationFixerAgent(MagicMock())._build_fix_prompt(task, ["bad"], {1: []})

    assert REFERENCE_HEADER not in prompt


def test_batch_repair_prompt_includes_reference_for_issue_sources():
    issue = {"source": PRONOUN_SOURCE, "target": "坏译文", "error_messages": ["format"],
             "error_details": [], "target_lang": "zh-CN"}
    prompt = ReflexionFixAgent(MagicMock())._build_batch_prompt([issue], "2")

    assert REFERENCE_HEADER in prompt
    assert "GetSheHe: pronoun she or he by gender" in prompt


@pytest.mark.asyncio
async def test_single_repair_and_assessment_prompts_include_reference():
    handler = MagicMock()
    handler.generate_response = AsyncMock(return_value='{"verdict":"reasonable"}')
    agent = ReflexionFixAgent(handler)

    await agent._suggest_fix(PRONOUN_SOURCE, "坏译文", "analysis", "stellaris", "zh-CN")
    await agent._assess_possible_variation(
        PRONOUN_SOURCE, "译文", [], game_id="stellaris", target_lang_code="zh-CN")

    prompts = [call.args[0] for call in handler.generate_response.await_args_list]
    assert all(REFERENCE_HEADER in prompt and "GetHerHis" in prompt for prompt in prompts)


def _capture_help_agent(monkeypatch):
    class CapturingAgent:
        def __init__(self, _model, **kwargs):
            self.instructions = kwargs.get("instructions", "")
            self.tools, self.validators = {}, []

        def tool(self, function):
            self.tools[function.__name__] = function
            return function

        def output_validator(self, function):
            self.validators.append(function)
            return function

    monkeypatch.setattr(help_agent, "Agent", CapturingAgent)
    monkeypatch.setattr(help_agent, "build_help_model", lambda *args, **kwargs: (object(), {}, None))
    return help_agent.build_help_agent("offline-test")


@pytest.mark.asyncio
async def test_help_agent_lookup_tool_records_results_and_grounds_answer(monkeypatch):
    agent = _capture_help_agent(monkeypatch)
    deps = HelpDeps()
    context = type("Context", (), {"deps": deps})()

    result = await agent.tools["lookup_localization_commands"](
        context, game_id="hoi4", names=["GetNameDefCap", "GetNothing"])
    answer = await agent.validators[0](context, HelpAnswer(reply="GetNameDefCap prints ...", confidence="high"))

    assert "lookup_localization_commands" in agent.instructions
    assert result["results"][0]["base"] == "GetNameDef"
    assert result["results"][1] == {"name": "GetNothing", "found": False}
    assert deps.command_lookups["hoi4"] == result["results"]
    assert answer.confidence == "high"


@pytest.mark.asyncio
async def test_help_agent_lookup_tool_bounds_input(monkeypatch):
    agent = _capture_help_agent(monkeypatch)
    context = type("Context", (), {"deps": HelpDeps()})()

    result = await agent.tools["lookup_localization_commands"](
        context, game_id="stellaris", names=["X" * 500] * 50)

    assert len(result["results"]) == help_agent.MAX_COMMAND_LOOKUPS
    assert len(result["results"][0]["name"]) == 80
