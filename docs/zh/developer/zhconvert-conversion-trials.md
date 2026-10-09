# 繁化姬：既有样本转换对照

这是外部确定性转换的实验工具，读取 Remis Agent API 的冻结材料，结果写入独立实验目录。
它不是产品的翻译 job，也不将外部结果伪装成 Luna 的模型译文。没有项目、词典、校对或输出目录写回。
目前限定 Surviving Mars CSV 参考文本；其它游戏需要明确扩展适配器，不宣称自动支持。

```powershell
python -m scripts.developer_tools.remis_converter_trial `
  --base http://127.0.0.1:1456 `
  --review-jobs review_bbd3b249e851413393c8b74b6279cdba review_c19d4620a3f341bcbcacb43904e96087 `
  --peer-job batch_f06cae7887944b5cb6308c3cf0e8aba5 `
  --term-release-id terms_32b9dd5d19b44dc82d8df3f5 `
  --expected-count 40 `
  --output J:\SurvivingMarsModdingNotes\traditional-base-audit-20261005\zhconvert-trial-20261006-v1
```

每次先 preflight，记录正式 Release 检查。输入来自既有 review entries（英文、官方参考、Luna 候选），
对照来自另一个原生模型 job；按精确源 ID 与相同英文匹配，拒绝空参考、重复条目、数量变化和缺少译文。
替换样本或模型时使用新目录，并通过 candidate-label/peer-label 正确标注模型及推理配置。
表内模型原先直接翻英文，而繁化姬转换简中；输入不同，不能当作同输入模型排名。

转换只发送参考文本，不发送编号、CSV 容器、凭据、英文答案或复杂自然语言指令。
配置固定为 Taiwan、默认自动模块、关闭文本清理；通过 userProtectReplace 保留原有游戏 tags 与转义换行。
全部语义 token 保留原形，没有发送给 LLM，更没有以不透明变量替代语义 token。
词典快照只用于本地技术检查，不在转换后替换词条。原样候选用来测转换器本身。

保留 INPUTS、preflight、service-info、词典、模型材料、逐条请求/raw_body/响应、comparison JSON 和可搜索 HTML/Markdown。
原始请求和服务版本参与 hash；同输入与同版本重跑直接读已保存的逐条响应，不重复 POST。
失败应答也保存，不自动重试；改变设置、版本或输入时换目录。中断后不确定的请求不会静默重发。
技术校验分别比较简中输入→转换输出和英文→转换输出；规则通过不表示语言、机制或术语准确。

本程序使用了[繁化姬 API 服务](https://zhconvert.org/)；繁化姬商用必须付费。
需要产品集成时另核对[服务说明](https://docs.zhconvert.org/api/0-getting-started/)及适用条款。
服务端转换引擎并未开源；公开客户端仅封装在线 API，不能作为本地引擎分发。

2026-10-06 的 40 条试验：全部得到非空输出，转换前后 tags/newlines 校验 40/40 通过；
无付费模型调用、无词典替换、无项目译文写回。实际服务版本 dict-7ea9895f-r1133，
模块和配置以逐条响应为准。三个 focused tests 覆盖语义 token、精确匹配及失败/空应答。
