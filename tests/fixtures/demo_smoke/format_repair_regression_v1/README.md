# Victoria 3 格式修复回归冒烟夹具 v1

这个夹具固定了乌托邦计划多语言更新中暴露过的格式损坏和误判案例。
它是测试输入，不是可直接发布的本地化包。

## 文件

- `localization/english/format_repair_demo_l_english.yml`：完整英文源文。
- `localization/simp_chinese/format_repair_demo_l_simp_chinese.yml`：简体中文损坏样本和合理改写样本。
- `localization/french/format_repair_demo_l_french.yml`：`#blue` 损坏、换行丢失和中文残留。
- `localization/polish/format_repair_demo_l_polish.yml`：`#bold` 损坏、俄语残留、换行和动态 token 变更。
- `localization/turkish/format_repair_demo_l_turkish.yml`：`#italic` 被改成 `#b`、混合西里尔字母和换行丢失。
- `localization/russian/format_repair_demo_l_russian.yml`：`$...$` 边界损坏、额外换行和 `#blue` 损坏。
- `manifest.json`：每个案例的类别、损坏译文、期望修复结果和判定方式。

## 案例语义

`manifest.json` 中的 `kind` 有四种含义：

- `repair`：必须修复，`expected` 是固定的期望译文。
- `review`：当前译文故意保持不变；模型应报告“合理改动”或“源文本问题”，并将其关闭，不能为了 token 数量相等而改写。
- `control`：合法对照组，不能被格式修复器改写。
- `report_only`：非法 key，只能报告并交给人工处理，不得调用模型。

覆盖的回归类别包括：

- `#BOLD` → `#b OLD`；`#blue` → `#b lue`；`#bold` → `#b old`；`#italic` → `#b`；
- 缺失或多出的 `#!`；
- `$...$`、`[...]` 的缺失、改名和边界损坏；
- 把完整动态 token 替换成 `[变量1]` 等不透明占位符后的损坏结果；
- 转义换行 `\\n` 的缺失和多余；
- 法语中的中文残留、波兰语中的俄语残留、土耳其语中的混合西里尔字母；
- 动态姓名因目标语言合并重复主语而合理减少；
- 源文自身格式不平衡；
- 引号仅作为序列化边界的合法对照。

特别注意：`placeholder_context` 是模型输出已经损坏后的回归样本。发送给模型之前，
仍必须保留完整的 `$...$`、`[...]` 和 `#tag` 上下文，不能把它们遮罩成通用占位符。

## 运行

```powershell
python -m pytest -q tests/test_format_repair_smoke_fixture.py
```

测试不会调用模型，也不会修改真实 Mod。需要在格式修复台手动回放时，应将整个
`localization` 目录作为 Victoria 3 项目的翻译目录，并以 `manifest.json` 作为修复后验收契约。
