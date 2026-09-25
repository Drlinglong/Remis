# Remis 3.2.1

发布日期：2026-09-25。正式安装包以 GitHub Release 附件为准。

## English

## Highlights

- **Surviving Mars / Relaunched: first stable release of localization support.** Import a subscribed Mod's `ModContent.fpk` directly. Remis extracts its resources into an isolated workspace, discovers localization entries and supported hardcoded Lua text, and prepares a project for translation.
- **One multilingual Mod package.** Export either a lightweight translation-only companion that requires the original Mod, or a complete internationalized copy containing the original resources and reviewed Lua changes. The complete-copy option is recommended when supported hardcoded text needs rewriting. English, Simplified Chinese, French, German, Spanish (Spain), Polish, Portuguese (Brazil), Russian and Turkish are supported target languages.
- **Keep updating your own Workshop item.** Bind your published item's ID in Project Management. Subsequent exports retain that identity; the original author's publication ID is not reused. Uploading still requires the game's built-in Mod Editor. Remis does not upload automatically.
- **RimWorld and Project Zomboid support is Preview.** Initial import, translation and export adapters are available, but these two games have not received the same in-game validation as Surviving Mars. Their formats and workflow coverage will continue to improve, alongside further Surviving Mars support.
- **Easier model setup.** Add GPT-6 Luna, Sol and Astra to the supported catalog. Manually entered models no longer get trapped behind an unsupported built-in reasoning setting; use provider defaults or explicit custom parameters.
- **Better Agent workflows.** In-app help, the built-in Agent and Remis for Codex can find the game-specific import, translation, installation and publishing guidance. Agent workflows also gain language-shell configuration, Steam workbench description/cover versions, and guarded synchronization of reviewed translations.

## Compatibility and usage

- For Surviving Mars, select the original author's Mod as input. Install the exported folder under the appropriate game's local `Mods` directory. Enable both the original and a translation-only companion; enable the complete copy instead of the original when using that delivery mode. Multiple language work folders are translation records; the final export combines selected languages into one Mod.
- The Exotic Minerals Expanded complete-copy workflow was tested in-game by the user in Chinese, French and German. Updating its already-bound Workshop item was also confirmed. This validates that example, not every community Mod or arbitrary Lua program.
- Hardcoded-text discovery and rewriting are deliberately bounded. Unsupported or ambiguous Lua constructs require review. Full-copy distribution includes the source author's resources; preserve attribution and follow the original Mod's license and permissions.
- Game-specific proofreading remains incomplete for the new games. Older saved format-issue reports can retain historical findings after files have changed; inspect the current exported files and report provenance before applying repairs.
- Reuse one Remis project for the languages and publication identity of a source Mod. Re-importing the same source into another project does not allocate a different in-game copy ID; independent variants are not supported by this first release.
- Stable and the separate Agent Preview application channel keep independent identities and data directories. The two games marked Preview in this release are features of the stable application; they do not require installing the Agent Preview channel.

## Engineering quality and reliability

- Introduce extensible game adapters while preserving the existing Paradox workflows and translation archive compatibility. Persist an approved game version through project discovery and translation; block unresolved RimWorld conditional load folders.
- Add bounded FPK extraction, isolated preparation, source/manifest hashes, stable localization IDs, multilingual delivery validation and project-bound publication identities. The standalone extractor is also available in the public [remis-fpk repository](https://github.com/Drlinglong/remis-fpk).
- Preserve CSV paragraph breaks and Surviving Mars runtime tags. Fix reasoning-setting transitions for manually entered models and support the GPT-6 catalog entries.
- Integrate backend fixes for persistent project identity, resumable translation lineage, database migrations and task completion/error handling. Harden custom-language output paths, project sidecars and description archives; refuse destructive same-name source imports in the legacy entry point.
- Integrate frontend guards against stale recovery and archive-analysis responses after project changes. Keep workflow state in dedicated hooks and services.
- Retain recent dependency/security updates from the main branch. Align stable application/build version and release date, and exercise FPK decompression in the frozen-backend release smoke test.

## 中文

## 主要更新

- **火星求生 / 重制版：首版稳定本地化支持。** 可以直接选择已订阅 Mod 的 `ModContent.fpk`。Remis 会将全部资源解包到隔离工作目录，发现本地化条目和支持处理的 Lua 硬编码文本，再准备翻译项目。
- **一个包承载多种语言。** 可以导出依赖原 Mod 的轻量纯翻译补丁，也可以导出包含原资源和已审核 Lua 改造的完整国际化副本。发现需要改写的受支持硬编码文本时，建议选择完整副本。目标语言支持英文、简体中文、法语、德语、西班牙语（西班牙）、波兰语、葡萄牙语（巴西）、俄语和土耳其语。
- **持续更新同一个工坊项目。** 在项目管理中绑定自己的已发布条目编号，后续导出会保留该身份；不会沿用原作者的发布编号。上传仍需使用游戏自带的 Mod Editor 手动完成，Remis 暂不自动上传。
- **环世界与僵尸毁灭工程标记为 Preview。** 已提供初步导入、翻译与导出适配，但尚未获得与火星求生相同程度的游戏内验证。今后会持续完善这两个游戏及火星求生的格式覆盖和使用流程。
- **模型设置更顺畅。** 补充 GPT-6 Luna、Sol、Astra。手动填写新模型时，不会再因不支持的内置推理设置而无法保存；可以使用供应商默认设置，或明确填写自定义参数。
- **Agent 更容易找到并执行正确流程。** 内置帮助、内置 Agent 和 Remis for Codex 的资料包含各游戏的导入、翻译、本机安装和发布说明。Agent 流程同时补充语言套壳、Steam 工作台描述与封面版本管理，以及经过约束的已审核译文同步。

## 兼容性与使用说明

- 火星求生的输入请选择原作者的 Mod。将最终导出的文件夹安装到对应游戏的本地 `Mods` 目录：纯翻译补丁需要同时启用原 Mod；完整副本则替代原 Mod 启用。各语言工作目录用于维护翻译记录，最终导出会将所选语言合并到一个 Mod 包。
- 本次使用“奇异矿物扩展”完成完整副本流程，用户已在游戏中验证中文、法语和德语，并确认绑定后的发布会更新同一个工坊条目。该结果不代表所有社区 Mod 或任意 Lua 代码均已验证。
- 硬编码发现和改写有明确支持范围；不支持或含糊的 Lua 写法仍需人工复核。完整副本包含原作者资源，应保留署名，并遵守原 Mod 的许可与授权要求。
- 新增游戏的专用校对能力仍不完整。旧的格式问题报告可能在文件改变后保留历史记录，修复前应核对当前导出文件及报告来源。
- 同一源 Mod 的多种语言与发布身份请维护在同一个 Remis 项目中。重复导入到另一项目不会分配不同的游戏内副本 ID；首版暂不支持据此创建彼此独立的变体。
- stable 与独立 Agent Preview 应用通道仍使用各自的应用身份和数据目录。本版两个游戏的 Preview 标记属于 stable 应用中的功能状态，不要求安装 Agent Preview 通道。

## 工程质量与可靠性

- 建立可扩展游戏适配接口，保留现有 P 社流程与翻译归档兼容性。审批时指定的游戏版本贯穿项目发现与翻译；环世界条件加载目录无法确认时会阻止翻译。
- 加入有限额的 FPK 解包、隔离准备、源文件与清单哈希、稳定本地化 ID、多语言交付校验，以及绑定到项目的发布身份。解包工具也已拆分到公开的 [remis-fpk 独立仓库](https://github.com/Drlinglong/remis-fpk)。
- 保留 CSV 段落换行和火星求生运行时标签；修复手动模型的推理设置切换，并补齐 GPT-6 模型目录。
- 合入后端项目持久身份、翻译恢复链路、数据库迁移和任务成功/失败状态处理修复；补强自定义语言输出路径、项目元数据和描述归档边界，拒绝旧入口破坏性覆盖同名源目录。
- 合入前端跨项目切换后的恢复与档案分析过期响应保护；工作流状态继续由独立 hook 和服务承担。
- 保留主分支近期依赖与安全更新；统一 stable 应用和构建版本、发布日期，并在冻结后端的发布冒烟中验证 FPK 解压。

## 发布验证记录 / Release validation

- Integrated backend baseline: 2,196 tests passed, 11 skipped; compilation, critical Flake8 checks and the Python architecture guard passed. Frontend: 1,028 tests in 247 files passed. Website: 64 tests, lint and build passed. Frontend lint has zero errors and 13 existing warnings; production dependency audits reported zero vulnerabilities.
- Five-theme visual checks passed for the Mars import workflow. The real Exotic Minerals Expanded archive was compared against 56 independently exported source files, including image resources; every file matched byte for byte. The reference Mod is not distributed with the source repository or test fixtures.
- Frontend responsibility review: new import/delivery components are 161/111 lines and contain 1/0 state hooks and no effects. Their API/workflow hooks are 54/51 lines (1/2 state hooks, 2/1 effects). Recovery remains a dedicated 259-line hook; archive analysis grows from 417 to 500 lines without adding state/effects or another responsibility. Initial translation flow grows from 228 to 266 lines, adds no state hooks and adds two effects for mounted/project lifecycle guards. Focused recovery tests cover failed status checks, delayed responses, project changes and React StrictMode.
- 后端、前端与网站测试均不调用付费模型。游戏内结果仅采用用户确认的火星求生中法德实测；环世界与僵尸毁灭工程仍为 Preview。

- Follow-up security and frozen-module checks are documented in the [release security review](https://github.com/Drlinglong/Remis/blob/main/docs/zh/developer/release-v3.2.1-security-review.md); final CI results are attached to [PR #220](https://github.com/Drlinglong/Remis/pull/220).
