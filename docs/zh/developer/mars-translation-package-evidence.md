# 火星求生独立翻译包：实现与验收记录

核验日期：2026-09-25。此文件是开发验收记录，不进入普通用户答疑语料。
现行操作指南见 [Surviving Mars 用户指南](../user-guides/surviving-mars.md)，
Agent 字段契约见 [API 参考](../../../.agents/skills/remis-agent/references/api-workflow.md)。

## 实现范围

项目概览提供独立翻译包预览和生成入口；GUI 与 Agent API 调用同一工作流服务。
输入只能是该项目登记的目标语言翻译目录，输出写入 Remis AppData 下的
`translation_packages/<project-hash>/<plan-id>/<mod-id>`，不写游戏目录。
已有 CSV 翻译/增量/校对流程和 job 的 CSV export-preview 保持兼容。

新包只包含匹配的 CSV、`metadata.lua` 和 `items.lua`。读取源 Mod 的字面量 ID/title，
不执行源 Lua；依赖原 Mod ID，major/minor 要求保持默认 0。翻译包 ID 由原 Mod ID
和语言决定，不随 Mod 元数据版本变化。设置 `optional_mod=true`，翻译包本身不成为
存档的必需游戏内容；包对原 Mod 的依赖仍是 `required=true`。

计划指纹绑定输入哈希、选项及生成文件的路径和内容哈希。生成前再次核验项目归属、
输出目录关联和指纹；旧计划、跨项目计划、改动后的输入、覆盖已有目录均被拒绝。
检查 ASCII 文本 ID、非 Translation 列、标签参数/数量和跨文件翻译冲突。
缺译文报错；缺少整个对应译表时只允许带明确警告的部分包预览。

## 游戏加载依据

读取本机 Relaunched 安装中的官方 `ModTools`，未修改游戏安装文件：

- `Docs/ModItemLocTable.md.html`：五列 UTF-8 CSV，第三列为译文。
- `Src/CommonLua/Modding/Mod.lua`：`UpdateLocTables`、`ModsLoadLocTables`、
  `ModDependency`；本机 SDK 的 `ModMinLuaRevision` 和 `ModRequiredLuaRevision` 均为 350453。
- `Src/CommonLua/Modding/ModItem.lua`：`ModItemLocTable` 的 filename/language 字段。
- `Src/CommonLua/Core/localization.lua`：`zh-CN` 对应 `Schinese`。

CSV 在包内位于 `Localization/Schinese/ModTexts.csv`；两个 Lua 注册文件使用
`Mod/<翻译包ID>/Localization/Schinese/ModTexts.csv` 虚拟挂载路径。
仅有 items.lua 或裸 CSV 相对路径不足以满足此加载器契约。
以上是 SDK 契约验证，尚未通过实际游戏启动验收。

## 真实项目结果

项目：Exotic Minerals Expanded - 简体中文，原 Mod ID `kz4dEz`。
调用前 preflight 成功；当前开发版 3.2.1，最新正式 Release v3.2.0，无更新提示。
通过 `/api/agent/projects/{project_id}/translation-package` 完成生成，返回
`allowed_actions=[inspect_local_output]`、`runtime_verified=false`。

- 3 个文件，共 **13,195 bytes**；原 Mod **9,722,533 bytes**，比例约 **0.14%**。
- CSV 49 条；47 条包含中文，2 条格式模板保持现有译文。
- 用独立标准 CSV 读取核对 ID、Text、VoiceActor、Context、Translation 以及标签顺序/参数；全部一致。
- 导出前后对原游戏 Mod、Remis 源副本和译文目录逐文件计算 SHA-256，均未变化。
- 本次打包不调用任何模型。此前译文来自用户授权的 OpenAI `gpt-6-luna` 工作流。
- 硬编码 `Untranslated(...)` 不属于 CSV 覆盖范围；不能据此包声称整个 Mod 已全部汉化。

真实产物与 verification.json 保存在忽略的 `.runtime/translation_packages/` 中，未加入 Git。
没有安装、覆盖、上传或发布 Mod；用户需复制整个包目录、启用两份 Mod，并选择简体中文实测。

## 验证与职责复核

后端聚焦回归 **141 passed, 2 skipped**，跳过项为本机无法创建的 symlink 测试。
覆盖 Agent API、游戏支持、输出预览、文档/Copilot、真实 builder 路由集成、CSV 和计划保护。
前端 hook/面板/项目入口/主题契约/文本完整性共 16 项通过，11 项语言一致性检查通过。
完整前端 lint/build 通过；13 条既有 lint warning 位于未修改的旧组件，本次组件无新增 warning。
Python 架构检查和 compileall 通过。浏览器确认 1 个 CSV/49 条、默认简体中文及三文件预览；
当前主题截图可读，另外四主题验证为共享颜色契约测试，未声称逐主题人工截图验收。

后端拆为元数据解析 147 行、包构建/校验 618 行、工作流 158 行及薄路由。
包模块超过 500 行后已做职责复核：Lua tokenizer 独立，项目持久化/计划审批/HTTP 均在模块外；
其余职责围绕单个文件包的校验和原子生成，不增加架构 baseline 例外。
ProjectDashboardView 从 199 增至 205 行，不增加 state/effect；新增组件均 25–69 行。
useTranslationPackage 145 行，包含一个聚合 state、一个请求序号 ref、一个可取消请求 effect；
面板仅有 opened 状态。API 状态和并发归属在 hook，传输在 service，展示分为表单、预览和结果组件。

## 用户实机反馈与换行修复（2026-09-25）

用户安装后通过截图确认该独立包能够加载并显示中文，同时报告描述中的字面 `\n`。
复核源表发现 3 条包含真实换行；既有译文中 2 条变成了字面转义，另 1 条的分段被模型省略。
问题发生在共享文本恢复层：`restore_special_tokens` 原先无条件使用 Paradox 的 `\\n`
写法，CSV writer 只是原样保存。此前的标签和列一致性检查没有覆盖段落结构。

新增显式换行恢复策略，火星批量、单条和修复路径使用真实 LF；Paradox 默认行为保持不变。
不全局解码字面 `\n`，防止修改原文有意表达的反斜杠序列。CSV 校验器和包生成检查原译文
的连续换行结构及新增字面转义；缺失分段不能再被视为通过格式检查。

用户明确批准后，通过受批准与 revision 约束的 Agent 校对保存接口修正 3 个 ID：
`471437516394`、`790136912627`、`286511341322`。随后读取校对结果，确认当前译文与
归档基线同时更新；仅换行改变，其他 46 条、正文、标签和非 Translation 列均未改动。
重新经标准 API 导出并替换已安装翻译 Mod 的 CSV：真实 LF 共 11 个，字面 `\n` 为 0，
新包共 13,196 bytes。原游戏 Mod 与 Remis 源副本未修改，旧 CSV 备份在忽略的
`.runtime/newline-fix-backups/20260925T034223Z/`，附 verification.json。
没有再次调用翻译模型；修复后的分段效果仍需用户重新加载游戏确认。

本次回归 145 passed、2 skipped（Windows symlink 权限），架构检查和 compileall 通过。
Agent 保存复用既有写回与归档同步，额外要求批准、非空文件 revision，且只接受项目内的
translation 文件。没有新增前端状态或组件。Reflexion batch 修复函数的解析职责提取为 helper，
低于 120 行后同步移除旧架构例外。
