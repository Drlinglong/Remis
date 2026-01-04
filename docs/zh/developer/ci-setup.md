# 轻量级本地 CI 使用说明

## 📦 已创建的文件

### 1. **独立检查脚本**（推荐先用这个）
- `check_before_commit.bat` - 双击运行的批处理文件
- `check_before_commit.ps1` - PowerShell 主脚本

**使用方法**：
```bash
# 方式1：双击运行
# 直接双击 check_before_commit.bat

# 方式2：命令行运行
.\check_before_commit.bat

# 方式3：直接运行 PowerShell（如果你喜欢）
powershell -ExecutionPolicy Bypass -File check_before_commit.ps1
```

### 2. **Git Pre-commit Hook**（可选，自动化）
- `pre-commit.example` - 示例 hook 文件

**安装方法**：
```bash
# 复制到 .git/hooks/ 目录
copy pre-commit.example .git\hooks\pre-commit

# 注意：Windows 上需要安装 Git Bash 或 WSL 才能运行 bash hook
```

---

## ⚡ 脚本功能

### ✅ 检查项目
1. **Python 后端测试** (`pytest`)
   - 运行所有79个单元测试
   - 报告失败的测试用例

2. **前端代码规范** (`eslint`)
   - 检查 React 代码风格
   - 报告语法和规范错误

3. **Git 状态检查**
   - 确认有文件变更
   - 显示待提交文件列表

### 🎨 输出示例

**全部通过**：
```
===========================================
  Pre-Commit Quality Check
===========================================

[1/3] Running Python Tests (pytest)...
  ✓ Python tests PASSED

[2/3] Running Frontend Linting (ESLint)...
  ✓ ESLint checks PASSED

[3/3] Checking Git Status...
  ℹ Modified files detected:
   M scripts/routers/glossary.py
   M tests/test_structured_parser.py

===========================================
  ✓ ALL CHECKS PASSED!
  Ready to commit!
===========================================

Completed in 3.42 seconds

Auto-commit changes? (y/N):
```

**检查失败**：
```
===========================================
  Pre-Commit Quality Check
===========================================

[1/3] Running Python Tests (pytest)...
  ✗ Python tests FAILED
  tests/test_example.py::test_something FAILED

===========================================
  ✗ CHECKS FAILED!
  Please fix the errors above before committing.
===========================================

Completed in 1.87 seconds
```

---

## 🔧 配置 ESLint（如果还没配置）

在 `scripts/react-ui/package.json` 中添加：

```json
{
  "scripts": {
    "lint": "eslint src --ext .js,.jsx,.ts,.tsx"
  }
}
```

如果没有 ESLint 配置，安装：
```bash
cd scripts/react-ui
npm install --save-dev eslint @eslint/js
npm init @eslint/config
```

---

## 🚀 推荐工作流

### 方案 A：手动检查（灵活）
```bash
# 1. 写代码...
# 2. 运行检查
.\check_before_commit.bat

# 3. 如果通过，选择自动提交或手动提交
```

### 方案 B：自动检查（严格）
```bash
# 1. 安装 pre-commit hook
copy pre-commit.example .git\hooks\pre-commit

# 2. 正常提交，hook 会自动运行
git commit -m "feat: add new feature"

# 3. 检查失败会自动中止提交
```

---

## 💡 下一步优化

1. **添加类型检查**：集成 `mypy` 检查 Python 类型注解
2. **自动格式化**：在提交前运行 `black` 和 `prettier`
3. **测试覆盖率**：生成覆盖率报告
4. **性能基准**：检测性能回归

---

## ⚠️ 注意事项

1. **首次运行较慢**：pytest 需要初始化，大约 2-3 秒
2. **跳过检查**：紧急情况下可用 `git commit --no-verify`
3. **PowerShell 权限**：如果遇到权限问题，运行：
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```

---

## 🎯 建议

**现在开始用独立脚本**，习惯后再决定是否自动化成 hook。双击 `check_before_commit.bat` 试试吧！
