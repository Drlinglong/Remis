# Documentation Status

这份文件用于说明 `docs/` 中哪些文档更适合当作当前入口，哪些更适合当作历史记录或专题实现笔记。

## 建议优先阅读

### 当前入口

- 根目录 `GEMINI.md`
- `docs/documentation-center.md`
- `docs/zh/index.md`
- `docs/en/index.md`
- `docs/archive/README.md`

### 当前协作与维护

- `docs/zh/developer/refactor_decision_guide.md`
- `docs/zh/developer/ci-setup.md`
- `docs/zh/developer/development-setup.md`
- `docs/zh/developer/build-release-script-guide.md`
- `docs/zh/developer/feature_flags.md`

## 作为专题参考阅读

这类文档通常有价值，但更适合在修改对应模块时按需查阅：

- 响应解析相关重构说明
- 并行处理相关实现说明
- 标点处理、动态验证器、Gemini CLI 集成等专题文档

## 作为历史记录阅读

以下文档可能仍有背景价值，但不应默认当作“当前事实”：

- `docs/agent.md`
- `docs/en/agent.md`
- 一些较早的架构总览文档
- 某些面向特定版本或特定发布阶段的报告
- `docs/archive/` 下的归档文档
- `docs/archive/developer-history/` 下的开发历史文档

## 使用原则

- 当文档与当前代码冲突时，以当前代码为准。
- 当文档与根目录 `GEMINI.md` 冲突时，以 `GEMINI.md` 为准。
- 当某份文档明显描述的是一次重构或一次版本演进，应将其视为“历史决策记录”，而不是永久规范。
- 当一份文档已移动到 `docs/archive/`，说明它已退出主入口，不再作为默认阅读材料。
