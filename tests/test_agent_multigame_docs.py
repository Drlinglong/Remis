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
    assert "game_version` on inspect is a one-time discovery hint" in skill
    assert "Remis persists it and uses it for discovery and translation" in skill
    assert "source resources remain read-only" in skill
    assert "do not call" in skill and "`approve-export`" in skill
    assert "translation-package/options" in skill
    assert "approved: true" in skill
    assert "does not execute incremental updates or package export" in skill


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


def test_incremental_preview_is_read_only_and_fingerprint_bound():
    skill = _read(".agents/skills/remis-agent/SKILL.md")
    reference = _read(".agents/skills/remis-agent/references/api-workflow.md")
    guide = _read("docs/zh/user-guides/incremental-update.md")
    for contents in (skill, reference, guide):
        assert "/api/agent/projects/{project_id}/incremental-preview" in contents
        assert "expected_preview_fingerprint" in contents
    for contents in (reference, guide):
        assert "Translation" in contents
    for contents in (reference, guide):
        assert "diff_executed: true" in contents
        assert "file_summaries" in contents
    assert "requires no provider" in reference
    assert "English baseline" in reference
    assert "original author's `Text`" in reference
    assert "优先使用作者原始 `Text`" in guide
    assert "source_language" in reference
    assert "source_language" in guide
    assert "GET /api/agent/jobs/{job_id}" in reference
    assert "GET /api/agent/jobs/{job_id}" in guide
    assert "西班牙语 `Text`" in guide
    assert "不会执行增量预览或翻译" in guide


def test_incremental_user_guide_explains_real_diff_dry_run_and_count_scopes():
    guide = _read("docs/zh/user-guides/incremental-update.md")
    assert "初次翻译的 `dry_run` 仍只是就绪检查" in guide
    assert "原文变化条目" in guide
    assert "实际提交模型条目" in guide
    assert "待人工复核条目" in guide
    quickstarts = (
        _read("docs/zh/developer/agent-api-quickstart.md"),
        _read("docs/en/developer/agent-api-quickstart.md"),
    )
    for contents in quickstarts:
        assert "/api/agent/projects/{project_id}/incremental-preview" in contents
        assert "expected_preview_fingerprint" in contents


def test_player_guide_distinguishes_help_and_incremental_workflows():
    guide = _read("docs/zh/user-guides/multi-game-localization.md")
    assert "展示初次翻译计划供用户审批" in guide
    assert 'Agent API 的 `workflow: "incremental"`' in guide
    assert "沿用 ModItemLocTable CSV 初次翻译和增量流程" in guide
    assert "隔离准备项目" in guide and "多语言本地交付" in guide


def test_surviving_mars_guides_match_the_csv_and_agent_contract():
    chinese = _read("docs/zh/user-guides/surviving-mars.md")
    english = _read("docs/en/user-guides/surviving-mars.md")
    english_flat = " ".join(english.split())
    api = _read(".agents/skills/remis-agent/references/api-workflow.md")
    for guide in (chinese, english):
        assert "ID,Text,Translation,VoiceActor,Context" in guide
        assert "leading zeros" in guide or "前导零" in guide
        assert "Translation`" in guide
        assert "ModContent.fpk" in guide
        assert "official Mod Editor" in guide or "官方 Mod Editor" in guide
        assert "custom_lang_config" in guide
    assert "文本标签" not in chinese
    assert "标签与标签之间的正文可以翻译" in chinese
    assert "尖括号内部的标签名称和参数不可翻译" in chinese
    assert "Text between tags may be translated" in english
    assert "tag names and parameters inside angle brackets must not be translated" in english
    assert "initial translation, incremental update and proofreading" in " ".join(api.split())
    for field in (
        "csv_contract",
        "source_column",
        "writable_column",
        "preserved_columns",
        "id_policy",
        "tag_policy",
        "preserve_relative_paths",
        "compressed_packages_supported",
        "recognized_resource_count",
        "recognized_entry_count",
    ):
        assert field in api
    assert "`Translation` may change" in api
    assert "Invalid/no-table scans have\nblocking diagnostics" in api
    for endpoint in (
        "/translation-package/options",
        "/translation-package/plan",
        "/translation-package",
    ):
        assert endpoint in api
        assert endpoint in chinese
        assert endpoint in english
    assert "metadata.loctables" in api and "ModItemLocTable" in api
    assert "required `ModDependency`" in api
    assert "Untranslated(...)" in api
    assert "runtime_verified: false" in api
    assert "Schinese" in api
    assert "metadata.loctables" in chinese and "metadata.loctables" in english
    assert "Mod/<generated package ID>/Localization/..." in english
    assert "Mod/<生成包ID>/Localization/..." in chinese
    assert "Untranslated(...)" in chinese and "Untranslated(...)" in english
    assert "49 rows" not in english and "47 行有中文译文" not in chinese
    assert "EXOTIC APPLICATIONS" not in english + chinese
    assert "%APPDATA%/Surviving Mars Relaunched/Mods" in english
    assert "%APPDATA%/Surviving Mars Relaunched/Mods" in chinese
    assert "当前此游戏的项目界面尚无专用可视化校对工作区" in chinese
    assert "预览通过后生成" in chinese
    assert "does not yet provide a dedicated visual proofreading workspace" in english_flat
    assert "review the preview before approving local output creation" in english_flat
    assert "a chat response does not perform preparation, translation, or export." in english


def test_translation_collection_docs_discovery_and_game_boundaries():
    guide_path = "docs/zh/user-guides/translation-collections.md"
    guide = _read(guide_path)
    skill = _read(".agents/skills/remis-agent/SKILL.md")
    api = _read(".agents/skills/remis-agent/references/api-workflow.md")
    index = _read("docs/zh/index.md")
    status = _read("docs/docs_status.md")
    assert guide_path in skill
    assert "## Translation collections" in api
    assert "translation-collections.md" in index
    assert "zh/user-guides/translation-collections.md" in status
    assert "only while that member Mod is enabled" in skill
    assert "cross-member global localization key conflicts" in skill
    assert "coverage is unverified and shown as a warning" in skill
    assert "可选 Mod" in guide and "原 Mod 仍需启用" in guide
    assert "Paradox 游戏" in guide and "冲突 key" in guide
    assert "translation completeness is" in api and "a warning" in api
    assert "other games receive" not in api
    assert "users follow each game's own Mod upload workflow" in api
    assert "Surviving Mars 的发布和更新" in guide


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
        contents = _read(relative_path)
        assert "multi-game-localization.md" in contents
        assert "surviving-mars.md" in contents

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
        "docs/zh/user-guides/surviving-mars.md",
        "docs/en/user-guides/surviving-mars.md",
        ".agents/skills/remis-agent/SKILL.md",
        ".agents/skills/remis-agent/references/api-workflow.md",
        "docs/zh/user-guides/translation-collections.md",
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


def test_fpk_reference_does_not_redirect_preparation_to_manual_editor():
    reference = _read(".agents/skills/remis-agent/references/api-workflow.md")
    assert "use the official Mod Editor to prepare an editable" not in reference
    csv_boundary = reference.split("CSV output preserves source-relative paths.", 1)[1].split("### Initial", 1)[0]
    assert "/api/agent/mars-pipeline/prepare/plan" in csv_boundary
    assert "tools/remis_fpk" in csv_boundary
    assert "Final FPK repacking and Workshop upload" in csv_boundary


def test_historical_mars_draft_and_code_version_guidance_are_explicit():
    history = _read("docs/zh/developer/release-v3.2.1-early-development.md")
    assert "status: historical" in history[:600]
    assert "../user-guides/surviving-mars.md" in history[:600]
    assert "3.2.1 未发布开发记录的唯一入口" not in _read("docs/docs_status.md")
    for relative_path in (
        ".agents/skills/remis-agent/SKILL.md",
        "docs/zh/developer/agent-api-quickstart.md",
        "docs/en/developer/agent-api-quickstart.md",
    ):
        assert "git rev-parse HEAD" in _read(relative_path)


def test_mars_preparation_authorization_is_discoverable_and_bounded():
    for relative_path in ("AGENTS.md", ".agents/skills/remis-agent/SKILL.md"):
        text = _read(relative_path)
        assert "Standing authorization for Surviving Mars preparation" in text
        assert "Do not ask for a" in text and "second authorization" in text
        assert "approved: true" in text
        assert "technical blocker, not missing permission" in text
        assert "does not itself authorize changing reader code" in text
    reference = _read(".agents/skills/remis-agent/references/api-workflow.md")
    assert "already authorizes bundled FPK inspection" in reference
    assert "do not require a duplicate" in reference
    assert "给 Agent 的常设授权" in _read("docs/zh/user-guides/surviving-mars.md")
    assert "Standing authorization for agents" in _read("docs/en/user-guides/surviving-mars.md")
