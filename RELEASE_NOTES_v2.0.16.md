# Release Notes v2.0.16 - Gemini Compatibility & Explorer Fix

- Fixed Google Gemini compatibility with older `google-genai` SDKs by retrying requests without `http_options` when the installed SDK does not support that argument.
- Pinned the minimum `google-genai` version in dependencies and added a build-time guard so outdated build environments fail fast instead of shipping a broken package.
- Improved Windows packaged builds by opening folders through `explorer.exe` instead of relying on `os.startfile()`, which had become unreliable in the Tauri sidecar environment.
- Updated application version metadata and in-app "Last updated" date for this release.
