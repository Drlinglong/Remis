# Release Notes v2.0.16

## English

- Fixed Google Gemini compatibility with older `google-genai` SDKs by retrying requests without `http_options` when the installed SDK does not support that argument.
- Pinned the minimum `google-genai` version in dependencies and added a build-time guard so outdated build environments fail fast instead of shipping a broken package.
- Fixed packaged Windows builds so folder opening uses `explorer.exe`, avoiding failures caused by `os.startfile()` in the Tauri sidecar environment.
- Fixed translation task state reporting so fully failed runs end as `failed`, partially recovered runs end as `partial_failed`, and final task status is pushed back to the frontend reliably.
- Improved progress reporting to show processed batches, successful batches, failed batches, and remaining batches more clearly.
- Updated application version metadata and in-app last updated date for this release.

## 中文

- 修复了 Google Gemini 在旧版 `google-genai` SDK 下的兼容性问题：当已安装 SDK 不支持 `http_options` 时，会自动回退为不带该参数的调用。
- 在依赖与构建流程中增加了 `google-genai` 最低版本限制，避免旧构建环境继续打出带缺陷的安装包。
- 修复了 Windows 打包版本中“打开文件夹”失效的问题，统一改为通过 `explorer.exe` 打开目录，不再依赖 Tauri sidecar 环境下不稳定的 `os.startfile()`。
- 修复了翻译任务状态回写问题：全部失败会正确显示为 `failed`，部分失败但已生成结果会显示为 `partial_failed`，最终状态会稳定同步回前端。
- 优化了翻译进度展示，新增已成功批次、已失败批次与剩余批次统计，避免“100% 但语义不清”的提示。
- 同步更新了本版本的应用版本号与内置“最后更新日期”。
