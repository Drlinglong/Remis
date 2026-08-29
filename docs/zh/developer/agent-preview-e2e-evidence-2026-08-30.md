# Remis Agent Preview v3.1.7 本地 E2E 证据

日期：2026-08-30

此记录只包含仓库内安全 Demo、机器标识符和相对输出路径。未记录 API key、用户私人 Mod 或私人绝对路径。

## 运行身份

- build channel：`agent-preview`
- version：`3.1.7-agent-preview.1`
- 开发数据目录名：`RemisAgentPreviewDev`
- provider/model：`openrouter` / `openai/gpt-5.6-luna`
- Copilot 输入上下文预算：`200000`
- reasoning：关闭；当前 OpenRouter 模型没有已验证的内置推理映射

## 输入与只读规划

用户目标：

> 请使用已有项目 Project Remis - Demo Mod - Stellaris，创建一个英译中的初次本地化计划并准备翻译。不要创建重复项目。

- 项目由仓库内 Stellaris Demo fixture 通过 Agent API 的 inspect、plan、approval 三段式流程导入。
- project ID：`dbc941f2-aef8-480f-8d82-7cf4aafb9d7f`
- Copilot chat：structured，strong grounding，high confidence，未裁剪历史
- 建议 action：`start_localization_workflow`
- PydanticAI planner：read-only；调用一次 `inspect_translation_context`
- typed recommendation：batch 1、concurrency 1、RPM 10、resume/main glossary/workshop 开启
- 服务端 translation plan：`ca7e1b56-3413-4ec7-a5f3-602a35b0b034`
- 未点击批准前未启动翻译；本次付费烟测经用户明确授权后批准

## 任务终态

- task ID：`c6da9873-d097-4d66-8117-f0419bd2dd45`
- started 与 completed 分开确认
- Task Center 权威终态：`completed`，100%
- backend 完整重启后，同一 task ID 仍返回 `completed`，100%
- validation：0 errors，2 warnings，0 条已报告 human-review item
- 两条 warning 均位于 `localisation/simp_chinese/remis_demo_events_l_simp_chinese.yml` 的 `remis_crisis.1.b:0`：
  - `validation_format_marker_parity_mismatch`
  - `validation_stellaris_color_tags_mismatch`
- 相对输出目录：`my_translation/zh-CN-test_project_remis_stellaris`
- 输出目录沿用了此前本地烟测目录，因此目录中保留了一份旧 validation report；本次报告是 `format_validation_report_20260830_093909.csv`。

## 当前输出 SHA-256

- `localisation/simp_chinese/remis_demo_events_l_simp_chinese.yml`：`E70A764A09EF335F4946A897988F7F3C407A1FA058A15179B7ED0560E1786EB4`
- `localisation/simp_chinese/remis_demo_tech_l_simp_chinese.yml`：`2A74478B3904CAB01B66B97E1DF6602038B187570C10ED63B7C9450B820947BA`
- `localisation/simp_chinese/remis_demo_traditions_l_simp_chinese.yml`：`46A177CDEEC29CE4804A537F06A1B13E470E86EF61A02B9EF30F76161B5650F9`
- `format_validation_report_20260830_093909.csv`：`4E34DC29E65ACF1F216EAD681BB5E7C8101D8163BBC83B93F7E55B976BA84F74`
- `workshop_issues.json`：`A1ED35EE3DD8F54B7DB647D621A43A3BD96A4D44274C8AA9230E948B35CBAAE0`

## 结论边界

- 这次证据证明自然语言入口、typed read-only planner、服务端 approval plan、真实付费翻译、Task Center 终态、validation 与重启后持久化闭环可用。
- `completed` 表示工作流到达终态，不代表输出零 warning；本次仍有两条需要人工复核的格式警告。
- 未构建安装包，未 commit、push、tag、发布或上传任何 artifact。
