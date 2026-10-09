# 火星本体混合语言补丁：高级交付 API

> 发布策略：原生 Batch 可供高级 Agent 使用；即时 trials、模型审阅、术语 coverage
> 和 base-patch 默认关闭。使用前核对 live capabilities，不得自动开启开关。
> 具体实验开关、重启要求及默认 403/发现限制见
> [高级 Agent API 策略](advanced-agent-policy.md)。


隔离开发功能，不包含在当前正式 v3.2.2。只构建本地可编辑 Mod；不调用模型、不安装、不上传 Steam，也不覆盖来源。
用于已有社区译文、官方中文转换结果与补译混合的本体补丁。普通 Mod 翻译仍使用既有 mars-pipeline。

## 操作

先调用 `/api/agent/preflight` 和 capabilities，确认 `mars_base_patch`。用户已经要求打包时可延续授权，导出时记录 `approved: true`。

`POST /api/agent/mars-base-patch/plan` 请求字段：

| 字段 | 内容 |
| --- | --- |
| project_id / file_id | 已注册本体英文五列 CSV 项目与源文件 ID |
| candidates_path / candidates_sha256 | UTF-8 JSON 的本地路径和经过审阅的 SHA256，最多 64 MiB |
| community_csv_path / community_csv_sha256 | 作者历史 CSV 与 SHA256；保留 ID/Text/Translation，允许官方额外列 |
| conversion_job_ids | 现有 `/chinese-conversion` 已完成任务 ID；逐项读取不可变输入和报告 |
| native_job_ids | 现有原生普通试译或 Batch 已收集任务 ID；逐项读取原文和收集结果 |
| cover_asset_path / cover_asset_sha256 | PNG/JPEG 封面及快照，复用既有 1 MiB 封面检查 |
| metadata | mod_id、title、description、short_description、last_changes、author |

Mod ID 限 ASCII 字母数字；标题限定 ASCII、最长 60 字符，避开游戏编辑器中文标题乱码。正文可以 UTF-8 中文。
候选 JSON 为 `{"entries": [...]}`；每项含 `id/source/official_sc/voice_actor/context/method/translation`。
method 支持 `old_community_exact`、`zhconvert_taiwan`、`native_luna_needed`。

来源核对要求：

- 所有非空英文 ID 必须完整覆盖一次，英文、官方中文、语音和语境必须与注册源文件完全一致。
- 历史译文必须匹配作者 CSV 的 ID、英文和译文；转换候选必须匹配真实 Remis 转换任务的输入和输出。
- 模型补译必须匹配已收集结果。已识别的后续字面改词，只接受有转换任务证明“原模型结果 → 当前候选”的链路。
- 候选不得丢失所选来源的游戏标签和换行。另对英文全量核对动态标签；只容许原文已有的强调、字体样式、换行排版差异。
- Mars 的方括号是显示文字，不按 Paradox 表达式解释；其中嵌套的 `<duration>` 等动态标签仍单独核验。装饰性 `<<< 新存檔 >>>` 同理。

返回 `status: ready`、计划 `id`、validation、文件 hashes 和 `allowed_actions`。保存这个计划，不手改其冻结快照。
`POST /api/agent/mars-base-patch/export`：`{"plan_id":"mars_base_...","approved":true}`。
成功后返回 `status: exported` 和 `output_path`，目录包含 metadata.lua、items.lua、Localization/Schinese/Game.csv 与封面。
独立 Mod 没有原作 Mod 依赖，也不复制现有 steam_id。内容为正体，加载入口是 Schinese。

## 重启、安装与发布

`GET /api/agent/mars-base-patch/plans/{id}` 可恢复计划和导出路径。计划与来源快照复用 Agent ledger/artifacts。
重复导出只在所有既有文件仍与快照一致时返回原结果；发现用户编辑、半成品或源文件变化立即停止，绝不覆盖。
receipt 在输出父目录，避免将内部审计材料打进玩家 Mod。

API 不安装。用户要求模组编辑器交付时，可按已返回的 `manual_install` 边界将输出复制到一个全新本地 Mod 目录，先检查目录不存在，复制后逐文件校验 hashes。
本地 J: 目录可以通过新的 AppData/Mods 目录联接进入编辑器；保留所有既有 Mods。不得以复制操作覆盖已有目录。
玩家启用补丁并选择游戏“简体中文”入口，重启后做字体、截断与语境抽查。API 检查不代表游戏运行验证或 Steam 上传成功。

此流程保留混合来源和交付记录，**没有向普通翻译的增量基线伪造写入模型作业**。更新补丁时重新准备受控候选，并生成新交付计划；旧计划与原始请求继续保留。

实现分层：`mars_base_patch_validation.py` 负责来源/完整性，`mars_base_patch_service.py` 负责冻结/渲染/交付，router 负责请求契约。
聚焦验证：`tests/test_mars_base_patch.py`，包含动态标签拒绝、来源链路、重复 ID、重启恢复和用户改动保护。
