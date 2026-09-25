from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_agent_skill_routes_through_dynamic_game_support_and_manual_install():
    skill = _read(".agents/skills/remis-agent/SKILL.md")
    assert "game_support" in skill
    assert 'workflow: "initial"' in skill
    assert 'workflow: "incremental"' in skill
    assert "game_version` is only a discovery hint" in skill
    assert "source resources remain read-only" in skill
    assert "do not call" in skill and "`approve-export`" in skill


def test_api_reference_documents_supported_formats_and_incremental_safety():
    reference = _read(".agents/skills/remis-agent/references/api-workflow.md")
    for contract in (
        "games[].game_support",
        "Keyed",
        "DefInjected",
        "rulesStrings",
        "restricted\nliteral Lua-table TXT",
        "source text must be English",
        "needs_review",
        "incremental_checkpoint_resume_supported",
        "validation_scope: \"artifact_presence_only\"",
        "409 unsupported_game_deployment",
        "Source files remain unchanged",
    ):
        assert contract in reference
    assert "Paradox initial translation" in reference
    assert 'workflow: "incremental"` rejects' in reference


def test_player_guide_distinguishes_help_and_incremental_workflows():
    guide = _read("docs/zh/user-guides/multi-game-localization.md")
    assert "展示初次翻译计划供用户审批" in guide
    assert 'Agent API 的 `workflow: "incremental"`' in guide
    assert "ModItemLocTable CSV 初次翻译、增量更新和校对流程" in guide


def test_user_and_developer_docs_link_to_the_single_api_contract():
    user_guide = "docs/zh/user-guides/multi-game-localization.md"
    api_reference = ".agents/skills/remis-agent/references/api-workflow.md"
    assert Path(ROOT / user_guide).is_file()
    for relative_path in (
        "docs/en/developer/agent-api-quickstart.md",
        "docs/zh/developer/agent-api-quickstart.md",
    ):
        contents = _read(relative_path)
        assert "game_support" in contents
        assert "multi-game-localization.md" in contents
        assert "unsupported_game_deployment" in contents

    for relative_path in ("README.md", "docs/README.md", "docs/README_ZH.md"):
        assert "multi-game-localization.md" in _read(relative_path)

    for relative_path in ("docs/agent.md", "docs/en/agent.md"):
        assert "Agent API" in _read(relative_path)
        assert "references/api-workflow.md" in _read(relative_path)

    assert Path(ROOT / api_reference).is_file()


def test_updated_documentation_has_no_broken_local_markdown_links():
    files = (
        "README.md",
        "docs/README.md",
        "docs/README_ZH.md",
        "docs/agent.md",
        "docs/en/agent.md",
        "docs/docs_status.md",
        "docs/en/developer/agent-api-quickstart.md",
        "docs/zh/developer/agent-api-quickstart.md",
        "docs/zh/user-guides/multi-game-localization.md",
        ".agents/skills/remis-agent/SKILL.md",
        ".agents/skills/remis-agent/references/api-workflow.md",
    )
    broken = []
    for relative_path in files:
        source = ROOT / relative_path
        contents = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", contents):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = (source.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                broken.append((relative_path, target))
    assert not broken
