# Project Remis v3.1.4

Released on 2026-08-14.

Version 3.1.4 is a hotfix for malformed source localization files and custom
language reporting.

## English

### Highlights

- A damaged localization entry with a clearly recoverable boundary no longer
  causes later valid entries in the same file to be lost. Remis writes an empty
  value for that damaged entry and continues the translation as a partial
  failure requiring attention.
- When a damaged file cannot be recovered safely, Remis skips that file and
  continues with the remaining files. A mod with no translatable files left is
  reported as failed.
- Translation completion messages now show the actual custom target language
  and its disguise language instead of the generic label `Custom`.

### Engineering quality and reliability

- Malformed quoted values are classified with the source filename, line number,
  and `unterminated_value` diagnostic instead of being reported as a silent
  success.
- Recovered empty values are written to both the generated localization file
  and the translation archive, while the original mod files remain untouched.

## 中文

### 主要更新

- 当损坏的本地化条目具有可明确判断的边界时，后续合法条目不会再被一并丢失。
  Remis 会为损坏条目写入空值，并继续翻译，同时将任务标记为需要关注的部分失败。
- 当损坏文件无法安全恢复时，Remis 会跳过该文件并继续翻译其余文件；如果整个 Mod
  已没有可翻译文件，则任务会明确报告失败。
- 翻译完成消息现在会显示实际的自定义目标语言及其伪装语言，不再只显示笼统的
  `Custom`。

### 工程质量与可靠性

- 损坏的引号值现在会携带源文件名、行号和 `unterminated_value` 诊断，不再静默显示
  成功。
- 恢复出的空值会写入生成的本地化文件与翻译归档数据库，原始 Mod 文件保持不变。
