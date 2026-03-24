# Release Notes v2.0.13

## 🇨🇳 中文更新日志
- **修复**: 解决了翻译进度卡在 100% 无穷加载的问题。
- **稳定性**: 禁用了处于试验阶段且不稳定的 **Agent Fixer** 组件，从底层切断了可能的递归崩溃。
- **验证器优化 (HOI4)**:
    - 改进了正则表达式边界，不再误将正文中的俄语单词误判为技术标签。
    - 完善了对 **俄语 (西里尔字母)** 的验证支持，大幅减少了在翻译俄语时的虚假报错。
    - 坚持技术标识符（如 `$VAR$`、`[Concept]`）必须为 ASCII 的规范，确保游戏引擎兼容性。

## 🇺🇸 English Release Notes
- **Fix**: Resolved the "infinite loading" issue where translation progress would hang at 100%.
- **Stability**: Disabled the experimental and unstable **Agent Fixer** component to prevent potential recursive crashes.
- **Validator Optimization (HOI4)**:
    - Refined regex boundaries to prevent misidentifying localized Russian words as technical tags.
    - Improved validation support for **Russian (Cyrillic)**, significantly reducing false positives during translation.
    - strictly enforced ASCII-only requirements for technical identifiers (e.g., `$VAR$`, `[Concept]`) to ensure game engine compatibility.
