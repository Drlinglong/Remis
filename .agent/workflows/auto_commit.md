---
description: local checks that mirror repository CI
---

# Local CI Check

当修改涉及代码、配置或构建逻辑时，提交前优先执行下面的最小检查流程。

## 1. 按改动范围运行检查

```powershell
python -m flake8 scripts tests --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest --tb=short

cd scripts/react-ui
npm run lint
npm run test
npm run build
```

Rust/Tauri 改动还需按 `docs/zh/developer/ci-setup.md` 运行格式与 `cargo check`。

## 2. 如果检查失败

- 先修复问题，再重新运行检查。
- 除非用户明确要求，否则不要带着失败结果提交。

## 3. 查看本次变更范围

```powershell
git status --short
git diff --stat
```

## 4. 提交策略

- 是否提交、是否推送，由用户当前指令决定。
- 不默认自动提交。
- 提交信息保持简洁即可，不需要额外套用复杂模板。
- GitHub Actions 是进入 `main` 的权威门禁；本地结果不能替代远端 CI。

## 5. 上下文来源

- 项目级上下文统一查看根目录 [GEMINI.md](../../GEMINI.md)。
- 如果历史流程描述与当前代码冲突，以当前代码和 `GEMINI.md` 为准。
