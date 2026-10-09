# 简繁与地区用语转换：高级 Agent API

这是长期可复用的产品服务，区别于只读的 40 条对照实验工具。暂不增加 GUI。
入口 `/api/agent/chinese-conversion`，使用繁化姬在线 API，无 LLM、无自然语言指令或语境词典。
支持明确的前后替换表、保护词和模块开关；这些规则不能理解“根据游戏机制选择正确词义”。
永不自动修改项目、词典、翻译基线、游戏文件或工坊内容。

先 GET `/api/agent/preflight`，确认正式 Release 检查及当前开发能力。
该接口目前只在隔离开发分支，正式 v3.2.2 不包含它。

## 接口

- GET `/service-info`：实时服务信息（15 分钟内可缓存）、转换器/模块、服务署名与收费说明。
- POST `/convert`：最多 100 条、合计 200,000 字符，编号由 Remis 本地保留。
- GET `/jobs?limit=50&offset=0`：发现过去转换记录，防止重跑。
- GET `/jobs/{id}`：持久状态、结果、结构诊断。
- GET `/jobs/{id}/artifacts/{kind}`：input/request/service/response/report，不接收文件路径。

```json
{
  "entries": [{"id":"001", "text":"<em>无人机</em>需要<resource(Metals)>。"}],
  "converter": "Taiwan",
  "pre_replace": {},
  "post_replace": {},
  "protected_words": [],
  "modules": {},
  "idempotency_key": "my-game-chinese-conversion-v1-001",
  "approved": true
}
```

converter 支持 Simplified/Traditional/Taiwan/China/Hongkong，另核对服务当下可用值。
替换仅支持字面值的单行字符串对，不接受 regex、自然语言或 term_release_id；未知字段报 422，不静默忽略。
模块名称来自 service-info，状态为 -1/0/1；`{"*":0}` 禁用全部模块。
approved 记录把给定文本发送至外部转换服务的授权；用户已经明确要求转换时沿用现有授权。

## 持久化与保护

复用现有 BatchRepository/BatchArtifacts，记录 kind=conversion，与 paid translation/review 分离。
输入、发送前状态、原始响应、版本、实际模块、解析与结构诊断全部保存。
同一幂等 key 与相同输入/设置直接读旧结果；不同输入报 409。不会因重启或失败自动重发。
若前一连接断开，先查 history，再按已保存 job ID 取结果。没有云端任务 ID 的未知请求不能云端取回，
接口不会声称提供 OpenAI Batch 那样的远端恢复能力。需要重试时核对旧状态，明确选新业务 key。

HTTP 请求固定为 HTTPS api.zhconvert.org，不允许任意代理 URL；不用 Remis 的 OpenAI/OpenRouter 凭据。
文本字符串以 JSON 数组序列化，输出严格核对条数/非空值，再映射本地编号；不把 CSV 或文件容器整块转换。
游戏标签、常见 Paradox 变量/表达式/格式标记、转义换行保持原形，并检查顺序、数量与换行。
这属于已识别 token 的技术检查，不能保证所有游戏自定义语法都被识别。
valid=false 的候选及原始响应仍可查，绝不自动写回。规则通过不代表语言或机制已正确。

## 服务条件

本程式使用了[繁化姬的 API 服务](https://zhconvert.org/)。响应始终含 attribution 和链接。
公开接口目前不要求 key；此前及本次实际请求均未配置 key。
[接入说明](https://docs.zhconvert.org/api/0-getting-started/)要求注明“繁化姬商用必须付费”，
但[商业页](https://docs.zhconvert.org/commercial/)又说目前尚没有商业收款计划；不能承诺永久免费或不限用途。
[服务条款](https://docs.zhconvert.org/license/)还要求保留免费字幕转换中附加的推广内容；本接口不会移除服务附加内容。
未来服务收费、限流或条款改变时，应刷新说明，而不是绕过限制。

## 开发与验证

schema、transport、受管服务、router 分开；没有前端 state/effect 增长。
生产模块均小于 200 行，没有提高架构 baseline。固定主机和请求 UTF-8 编码。
测试 tests/test_chinese_conversion_api.py 覆盖重启读回、幂等冲突、未知请求不重放、结构破坏、
少条/空应答、原始响应保留、外部 kind 不可读取以及不支持 LLM 指令；均为 fake transport，无外部收费。

2026-10-07 实跑：161 组共 16,012 条全量简中转换已通过这个 API 完成，输入→输出技术检查通过。
原生普通 Luna standard/max 的 58 条回应也已保留，不使用 Pro 或 Batch。纯样式/变量模板
原样返回是正确行为，batch collector 的 source-fallback 检查现排除这种无自然语言的 Mars 模板。
旧收集缓存可 POST `/api/agent/batch-jobs/{id}/collect?revalidate=true`：仅重验本地原始响应，
不联系模型、不重新收费，保留旧 collection hash；已 apply 的任务禁止更改其收集状态。

focused suite（Agent、Batch、词典、原生试译、审阅、候选复用、转换与纯模板）共 131 passed，
76 条既有 SQLAlchemy 弃用警告。compileall、架构检查、diff check 及新 Skill 校验通过。
schema 约 40 行、transport 约 50 行、持久服务约 120 行、router 约 50 行，没有 GUI 或 baseline 增长。

与传统模型翻译共存，但不接入普通模型 provider 下拉框，也不声称转换器是神经网络翻译模型。
后续 GUI 可以直接调用这些端点；项目级 apply/export 要另外接入既有受管流程。
