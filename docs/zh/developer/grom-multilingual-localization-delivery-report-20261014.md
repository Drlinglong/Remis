# Grom 七语言完整副本：交付与源码改动报告

交付日期：2026-10-14。原 Mod：[Grom / GromGor](https://steamcommunity.com/sharedfiles/filedetails/?id=3604444917)。

## 交付结果

已制作并部署独立完整副本 **Grom｜多语言本地化完整副本**，Mod ID 为 `Remise0e5b8600848`。以英文为源语言，新增简体中文、法语、德语、西班牙语、波兰语、巴西葡萄牙语和土耳其语，每种语言包含 **554 个唯一条目**。英文代码回退与原有俄语资源保留。

- [已安装的游戏 Mod 目录](<C:/Users/Drlin/AppData/Roaming/Surviving Mars Relaunched/Mods/Remise0e5b8600848>)
- [完整交付源码包](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/grom_delivery/20261014/Remise0e5b8600848>)
- [中文创意工坊描述](<J:/V3_Mod_Localization_Factory/docs/zh/user-guides/grom-multilingual-workshop-description.zh-CN.txt>)
- [架构问题与初步方案讨论文档](<J:/V3_Mod_Localization_Factory/docs/zh/developer/mars-localization-import-and-agent-review-proposal.md>)

中文描述已写入副本的 `metadata.lua`，同时填写更新说明并保留原封面。源工坊 ID 已移除，副本使用独立 ID，供游戏内 Mod 编辑器作为新项目发布。**没有执行 Steam 上传，也没有实测编辑器上传是否成功。**

部署创建了新的目录，没有覆盖现有 Mod，没有修改玩家存档或启用配置。请在游戏中停用原版 Grom 和针对它的其他翻译补丁，只启用本副本；切换已有存档前先备份。

## 源文件与原包保护

原始 FPK：`I:\SteamLibrary\steamapps\workshop\content\3215050\3604444917\ModContent.fpk`。

原包 SHA-256：`0f639d14c7e673de14140e0970ab73c4f9b7390579b56411d38f9fc1a15b6c58`。

原始只读解包目录：[grom-3604444917-20261014](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-3604444917-20261014>)。

审查改造后的输入目录：[grom-reviewed-source-20261014-v2](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-reviewed-source-20261014-v2>)。最终交付源码应以上面的完整交付源码包为准，它还包含导出、补充翻译和独立 Mod 元数据。

原作者的 Mod ID 为 `DoEpVdS`，本地源版本为 major 2 / revision 974。Steam 缓存和原始 FPK 未改动。最终包中的 104 个原有非 Lua、非 CSV 资源文件与原包逐字节一致。

## 遇到的问题及处理方式

原作者确实提供了俄语 `local.csv`。问题不是没有本地化表，而是它与代码中的可见文本不能完全对应：CSV 有引号前空格、缺少末尾空列，Text 列混合英俄文本；Lua 中还有无编号的 `T("…")`、直接写死的按钮和设置标签，以及少量共用编号的不同文本。

此次在隔离副本中按代码语义审查候选项，再用可重复脚本执行明确的局部改写。没有把所有英文字符串机械替换为翻译调用。资源路径、内部选项值、AI 动作标识、纯布局字符串和动态图片表达式按用途保留。

### Mod 源码改动

1. 将 CSV 规范化为完整的五列格式；已能确认英文来源的条目采用 Lua 中的英文回退作为源文，保留原俄语有效译文。
2. 为无编号的英文百科、按钮等文本分配 88 个新编号，并检查与原表和游戏词表的编号冲突。部分嵌套 `T({id, ...})` 规范为等价写法，便于现有提取器读取。
3. 将 `666277` 被名称与说明混用的问题修正为原俄语表已有的说明编号 `666278`。将另一处完整说明与简短说明拆分，新编号为 `938563342690`，并复制原俄语短说明，避免俄语回退退化。
4. 增加 19 个选项显示标签和 35 个 AI 动作显示标签映射。选项的内部 value、动作 ID 和相关判断保持原值；选项显示钩子仅作用于本副本。
5. 对不同用途的 Unknown 回退分别本地化。编辑器动态图片/描述及纯布局包装保持其原有表达式，使用局部别名避免把布局误计入自然语言翻译。
6. 导出时把 `Mod/DoEpVdS/` 资源路径改为副本 ID 的命名空间，并注册七种语言表。保留原作者署名和俄语注册。

准备阶段共修改 20 个源文件，包含 `local.csv` 及以下 Lua 文件；导出阶段另更新 `items.lua`、`metadata.lua` 和生成的语言表：

```text
Code/AlchemyLaboratory.lua
Code/common.lua
Code/droneHub.lua
Code/encyclopedia.lua
Code/names.lua
Code/notifications.lua
Code/rivals.lua
Code/someScript.lua
Code/speed.lua
Code/stirling.lua
Code/tech.lua
Code/techsTrading.lua
Code/tradePad.lua
Code/XDef/FastOptionsWindow.generated.lua
Code/XDef/SearchLandingSpotWindow.generated.lua
Code/XDefs.lua
Data/Tech.lua
Data/XDef/FastOptionsWindow.lua
Data/XDef/SearchLandingSpotWindow.lua
```

详细证据：[源码改写差异](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-reviewed-source.diff>)、[209 项改写决策](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-source-review-decisions.json>)。

## Remis 必要兼容修复

在用户明确允许修改项目源码后，于独立工作树 `J:\V3_Mod_Localization_Factory-worktrees\grom-export-sidecar-20261014` 实施下列修复，验证后同步至运行任务的 batch 工作树。交付时尚未提交 Git。后续已在 batch 工作树提交为 `6f4a485c`，并整合到 `codex/release-next-20261014-integration`；未推送或发布。原独立修复工作树已清理，补丁和新增测试另有清理归档，batch 源码及运行数据保留。

| 文件 | 修复内容 |
| --- | --- |
| `scripts/core/services/translation_package_workflow.py` | 改用现有 `read_project_sidecar` 服务，修正调用已不存在的项目管理器方法导致的导出 API 500。 |
| `scripts/core/mars_pipeline/prepare_source.py` | 区分 Lua 的 `..` 拼接与 `.` / `:` 成员调用；恢复拼接后的 `T(...)` 和 `T{...}` 提取，同时继续排除对象成员调用。 |
| `scripts/core/mars_pipeline/delivery_metadata.py` | 允许严格验证后的字面量 loctables 数组追加语言注册，保留原俄语；动态表达式、未知字段、不完整或重复定义继续拒绝。 |

对应测试修改：`tests/test_translation_package_api.py`、`tests/test_mars_prepare_source.py`，新增 `tests/test_mars_existing_loctables.py`。没有修改 FPK 阅读器边界，没有提高架构基线或关闭严格校验。

[Remis 修复差异](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-remis-fixes.diff>)记录已跟踪文件的修改；新增测试源码位于 batch 与整合工作树的 `tests/test_mars_existing_loctables.py`，已纳入上述提交。

这些是本案例的必要兼容修复，不代表讨论文档中的通用 Agent 语义审查架构已经实现。

## 翻译配置与补充交付

运行 Remis 3.2.2 的指定 `.runtime/app` 数据目录，服务绑定 `127.0.0.1:1463`。preflight 的官方版本检查成功，发现较新版本 [Remis v3.3.0](https://github.com/Drlinglong/Remis/releases/tag/v3.3.0)，已告知；没有更换用户的运行环境。

使用 OpenAI `gpt-6-luna`、high 推理强度，启用主术语表和嵌入式自动格式修复。简体中文采用现有火星词典 290（1711 个英/简中条目）；其他六种语言只匹配各自存在的目标术语，没有套用中文译名。此次没有新增繁体中文语言包。

首次启动时发现主术语表尚未实际指定，在五个成功批次后取消该任务，重新指定词典再完整翻译。已发生的调用可能计费；本次未提供经账单核对的费用总额。

主任务翻译 522 条；覆盖复核发现拼接表达式后的 32 条被提取器漏掉。修复提取器后，这些文本作为独立补充项目经 Remis 翻译。两个成功任务分别为：

- 主任务：`6a7a5256-d8c0-43f0-882b-9d68ba529ca3`，七语言 × 522 条。
- 补充任务：`f6b6ff10-4475-4208-a0be-f7bd001a88dc`，七语言 × 32 条。

最终每种语言 554 条，分布于 `local.csv`、`RemisLua.csv` 和 `RemisSupplement.csv`。主包通过 Remis API 导出；依照用户允许 skill 外操作的授权，随后在独立交付目录组装补充表并追加注册，**这一步不是标准导出 API 一次性生成**。原导出包与持久化项目状态保留，没有直接改数据库。

简体中文通过带版本检查的校对 API 修正了“投入资源”“产出资源”、术语“摩擦电洗涤器”和“Grom 模组设置”等四处文案。其他语言仍是未经过专业母语校对的机器翻译。

## 验证及边界

- 两个完成任务的 Remis 校验摘要均为错误 0、警告 0、待人工审查 0。
- 最终包七语言各有 554 个唯一 ID；英文源文与完整提取清单匹配，译文非空，格式标签和换行一致，未检出替换字符或连续问号乱码。
- 57 个 Lua 文件通过语法解析；选项标签映射经过隔离执行测试，验证内部值、其他 Mod 和未知标签回退保持原行为。
- 原表 394 个俄语有效译文全部保留，并为拆分的新短说明编号增加一条复制译文。
- 部署的 183 个文件与交付包逐文件 SHA-256 一致。
- 必要 Remis 修复的相关测试：**101 passed，2 skipped**；Python 架构检查和差异格式检查通过。

**未完成的验证：**没有启动游戏测试所有语言界面、功能行为或已有存档迁移，也没有执行 Steam 上传。静态检查不能证明游戏运行兼容性。554 条是本次按英文来源审查提取的覆盖范围，不保证所有条件分支或原表无代码引用的历史条目均已重新翻译。

证据文件：[最终包审计](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-final-package-audit.json>)、[组装记录](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-final-assembly.json>)、[本地部署回执](<J:/V3_Mod_Localization_Factory-worktrees/batch-term-workflow-20261005/.runtime/app/diagnostics/grom-deployment-receipt.json>)。
