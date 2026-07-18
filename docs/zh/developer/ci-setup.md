# CI、依赖维护与仓库门禁

Remis 使用 GitHub Actions 作为权威持续集成环境。本地检查用于缩短反馈时间，但是否允许进入 `main`，最终由 GitHub 上的 CI 状态和 repository ruleset 决定。

## 为什么从本地脚本迁移

早期项目只有单一维护者，质量检查主要依赖根目录的 `check_before_commit` 脚本和可选 Git hook。这些脚本有三个根本限制：

1. 是否运行完全依赖开发者自觉，无法形成仓库门禁；
2. 它们复用本机已经安装的依赖，不能证明干净环境可复现；
3. 脚本会检查工作区是否有改动，并可能在依赖不存在时跳过检查，因此不适合作为远端 CI 入口。

旧脚本已原样归档到 `archive/developer_tools/legacy_pre_commit/`，仅用于项目历史追溯。

## 当前工作流

### CI

`.github/workflows/ci.yml` 在 pull request、`main` push 和手动触发时运行三个稳定检查：

- **Python tests**：Windows + Python 3.10，安装 `requirements.txt`，运行源码编译、关键 Flake8 错误检查和完整 Pytest；
- **Frontend checks**：Ubuntu + Node.js 22，执行 `npm ci`、ESLint、Vitest 和 production build；
- **Rust checks**：Windows + stable Rust，执行 `cargo fmt --check` 和 `cargo check --locked`。

Rust job 会创建一个不进入 Git 的空 sidecar 占位文件。它只用于满足 Tauri 在 `cargo check` 阶段的路径验证；真正的 `web_server` sidecar 仍由 release build pipeline 生成。

### Dependency Review

`.github/workflows/dependency-review.yml` 检查 pull request 引入的依赖变化。当新增或升级的依赖包含 high 或 critical 级已知漏洞时，检查失败。

它不是对整个历史依赖树的替代扫描；现有依赖告警由 Dependabot alerts 和后续安全更新处理。

## Dependabot 策略

`.github/dependabot.yml` 覆盖四个生态：

- 根目录 Python/pip；
- `scripts/react-ui` 的 npm；
- `scripts/react-ui/src-tauri` 的 Cargo；
- GitHub Actions。

版本更新每月检查一次。minor 和 patch 更新按生态分组，major 更新保持独立 PR，每个生态最多同时打开两个普通版本更新 PR。安全更新单独分组，且不会自动合并。

Dependabot 只负责提出变更。CI 负责验证，ruleset 负责阻止不合格合并，维护者保留最终批准权。

## 仓库安全自动化

GitHub 仓库设置已启用：

- Dependabot alerts、dependency graph 和 automated security updates；
- secret scanning 与 push protection；
- private vulnerability reporting；
- CodeQL default setup，每周扫描 Python、JavaScript/TypeScript 和 Rust。

CodeQL 会显示在 pull request checks 中，但在跑出更长时间的稳定基线前不作为 required check。
Dependabot 安全更新只创建 PR，不会自动合并；仍需通过 CI 并由维护者决定是否合并。

## Main ruleset

`main` 应至少要求：

- 通过 pull request 合并；
- `Python tests`、`Frontend checks`、`Rust checks` 和 `Dependency review` 全部通过；
- 所有 review conversation 已解决；
- 禁止删除和 non-fast-forward push；
- 保持已签名提交要求。

Remis 当前主要由单一维护者维护，因此不强制一名外部 reviewer。管理员 emergency bypass 只用于仓库恢复，不应作为日常合并路径。

## 本地等价命令

### Python

```powershell
python -m compileall -q scripts tests
python -m flake8 scripts tests --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest --tb=short
```

默认测试不会访问真实模型 API。需要手工运行 Gemini 并发 smoke test 时，先显式设置
`REMIS_RUN_LIVE_MODEL_TESTS=1`；该测试可能产生外部 API 费用，不属于 CI 门禁。

### Frontend

```powershell
cd scripts/react-ui
npm ci
npm run lint
npm run test
npm run build
```

### Rust/Tauri

```powershell
cargo fmt --manifest-path scripts/react-ui/src-tauri/Cargo.toml -- --check
New-Item -ItemType File -Force scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe | Out-Null
cargo check --locked --manifest-path scripts/react-ui/src-tauri/Cargo.toml
```

这些命令可以按改动范围选择执行，但 pull request 上的远端 CI 不会因本地结果而跳过。

## 明确不做

- 不让 Dependabot 或其他 bot 自动合并 major 更新；
- 不在 CI 中调用付费模型、LM Studio、Ollama 或真实第三方 API；
- 不把开发者本机或 5090 配成公开仓库的普通 self-hosted runner；
- 不在普通 PR workflow 中构建完整 Windows installer；
- 不允许 CI 或机器人修改生产 prompt、glossary、模型默认值或用户数据；
- 不把通过 CI 等同于功能、翻译质量或安全性已经获得人工认可。

## 后续演进

后续可以逐步加入 release provenance、更严格的依赖锁定，并在 CodeQL 跑出稳定基线后评估是否将其设为 required check。新增门禁必须先在非阻塞状态运行，避免用不稳定检查锁死 `main`。
