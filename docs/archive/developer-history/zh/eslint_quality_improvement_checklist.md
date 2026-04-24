# ESLint 代码质量改进清单

## 📊 概述

**当前状态**: 前端代码存在 **59个 ESLint 警告**（已从45个错误降级）

**影响**:
- ✅ CI 检查能够通过（ErrorLevel = 0）
- ⚠️ 代码质量问题未解决，技术债累积
- 📈 长期会影响代码可维护性

---

## 🎯 问题分类

### 🔴 Critical（1个）- 必须尽快修复

#### 1. `no-undef` - 未定义变量
**文件**: `vite.config.js`  
**问题**: `process` 未定义  
**修复**: ✅ **已修复** - 添加了 `globals.node`

---

### 🟡 High Priority（44个）- 未使用的变量/导入

#### 问题分布

| 类型 | 数量 | 文件数 |
|------|------|--------|
| 未使用的导入 | ~15 | 10+ |
| 未使用的变量 | ~20 | 15+ |
| 未使用的参数 | ~9 | 8+ |

#### 典型案例

##### 2.1 未使用的导入
```javascript
// ❌ 问题
import { useTranslation } from 'react-i18next'  // 导入但未使用

// ✅ 修复
// 删除该行，或使用它
const { t } = useTranslation()
```

**受影响文件**:
- `src/App.jsx` (1处)
- `src/components/common/MonacoWrapper.jsx` (3处)
- `src/components/layout/AppSider.jsx` (1处)
- `src/pages/GlossaryManagerPage.jsx` (3处)
- `src/theme.js` (2处)

##### 2.2 未使用的解构变量
```javascript
// ❌ 问题
const { error } = await api.fetch()  // error 未使用

// ✅ 修复方案1：重命名为 _error
const { error: _error } = await api.fetch()

// ✅ 修复方案2：删除解构
await api.fetch()

// ✅ 修复方案3：真正使用它
const { error } = await api.fetch()
if (error) handleError(error)
```

**受影响文件**:
- `src/components/glossary/EditTermForm.jsx` (2处)
- `src/components/neologism/JudgmentCourt.jsx` (3处)
- `src/components/neologism/MiningDashboard.jsx` (1处)
- `src/components/tools/WorkshopGenerator.jsx` (1处)
- `src/hooks/useGlossaryActions.js` (5处)
- `src/hooks/useProofreadingState.js` (2处)

##### 2.3 未使用的 State 变量
```javascript
// ❌ 问题
const [logs, setLogs] = useState([])  // 完全未使用

// ✅ 修复
// 删除该行，或实际使用它
```

**受影响文件**:
- `src/pages/InitialTranslation.jsx` (8处)
- `src/pages/ProjectManagement.jsx` (1处)
- `src/components/tools/ThumbnailGenerator.jsx` (2处)

---

### 🟢 Medium Priority（15个）- React Hooks 依赖

#### 3. `react-hooks/exhaustive-deps` - useEffect 依赖缺失

**问题**: `useEffect` 中使用的函数/变量未添加到依赖数组

```javascript
// ❌ 问题
useEffect(() => {
  fetchData()  // fetchData 未在依赖中
}, [])

// ✅ 修复方案1：添加依赖
useEffect(() => {
  fetchData()
}, [fetchData])

// ✅ 修复方案2：使用 useCallback 包装
const fetchData = useCallback(() => {
  // ...
}, [])

useEffect(() => {
  fetchData()
}, [fetchData])
```

**受影响文件** (15处):
- `src/components/ApiSettingsTab.jsx` (1处)
- `src/components/glossary/EditTermForm.jsx` (1处)
- `src/components/neologism/JudgmentCourt.jsx` (1处)
- `src/components/project/ProjectSidebar.jsx` (1处)
- `src/components/tools/ProjectOverview.jsx` (2处)
- `src/hooks/useGlossaryActions.js` (2处)
- `src/hooks/useProofreadingState.js` (3处)
- `src/pages/InitialTranslation.jsx` (2处)
- `src/pages/ProjectManagement.jsx` (2处)

---

### 🟣 Low Priority（2个）- Fast Refresh 限制

#### 4. `react-refresh/only-export-components`

**问题**: Context 文件导出了非组件内容

```javascript
// ❌ 问题
export const SidebarContext = createContext()  // 导出常量
export const SidebarProvider = ({ children }) => { ... }

// ✅ 修复：分离文件
// sidebarContext.js - 只导出 Context
export const SidebarContext = createContext()

// SidebarProvider.jsx - 只导出组件
export const SidebarProvider = ({ children }) => { ... }
```

**受影响文件**:
- `src/context/NotificationContext.jsx`
- `src/context/SidebarContext.jsx`

---

### 🔵 Very Low Priority（2个）- 正则转义

#### 5. `no-useless-escape` - 不必要的转义

```javascript
// ❌ 问题
const pattern = /\./  // . 在字符类外不需要转义

// ✅ 修复
const pattern = /\./  // 保持原样（在某些上下文中需要）
// 或
const pattern = /./   // 如果确实不需要转义
```

**受影响文件**:
- `src/hooks/useProofreadingState.js` (2处)

---

## 📋 修复计划

### Phase 1: 快速清理（预计 1-2 小时）

**目标**: 减少 30+ 个警告

1. **删除明显无用的代码** (15个警告)
   ```bash
   # 删除未使用的导入
   # 删除未使用的 State 变量
   ```

2. **重命名未使用的错误处理** (10个警告)
   ```javascript
   const { error } = ... → const { error: _error } = ...
   ```

3. **删除未使用的事件参数** (5个警告)
   ```javascript
   onClick={(e) => ...) → onClick={(_e) => ...)
   ```

### Phase 2: 深度重构（预计 3-4 小时）

**目标**: 修复所有 useEffect 依赖问题

1. **提取 useCallback** (10个警告)
2. **重构 Context 导出** (2个警告)
3. **审查真正需要的依赖** (5个警告)

### Phase 3: 最终清理（预计 30 分钟）

1. **修复正则转义** (2个警告)
2. **代码审查和测试**
3. **更新 ESLint 规则为 error**

---

## 🎯 完成标准

- [ ] ESLint 警告数量 < 10
- [ ] 所有 `no-unused-vars` 警告已清理
- [ ] 所有 `react-hooks/exhaustive-deps` 已修复
- [ ] CI 检查在 error 级别通过（不再需要 warn 降级）

---

## 📁 受影响文件完整列表

### 按警告数量排序

1. **src/pages/InitialTranslation.jsx** (10个警告)
2. **src/hooks/useGlossaryActions.js** (7个警告)
3. **src/hooks/useProofreadingState.js** (5个警告)
4. **src/components/neologism/JudgmentCourt.jsx** (4个警告)
5. **src/pages/GlossaryManagerPage.jsx** (3个警告)
6. **src/components/common/MonacoWrapper.jsx** (3个警告)
7. **src/pages/ProjectManagement.jsx** (3个警告)
8. **src/components/tools/ProjectOverview.jsx** (2个警告)
9. **src/components/tools/ThumbnailGenerator.jsx** (2个警告)
10. **src/theme.js** (2个警告)
11. **src/context/NotificationContext.jsx** (1个警告)
12. **src/context/SidebarContext.jsx** (1个警告)
13. ... 其他文件各1个

---

## 🔧 自动化修复建议

### 可以自动修复的问题（~30个）

```bash
# 使用 ESLint 自动修复
npm run lint -- --fix

# 预计可自动修复：
# - 删除未使用的导入
# - 部分格式问题
```

### 需要手动修复的问题（~29个）

- useEffect 依赖（需要判断）
- 未使用的 State（需要确认逻辑）
- Context 导出（需要重构）

---

## 💡 建议

1. **不要一次性全部修复** - 分阶段进行，每次提交前跑 CI
2. **优先修复高频文件** - 如 `InitialTranslation.jsx`（10个警告）
3. **配合功能开发** - 修改某个文件时顺便清理其警告
4. **保持测试覆盖** - 修复后确保功能正常

---

## 🏷️ Labels

- `tech-debt`
- `code-quality`
- `frontend`
- `eslint`
- `good-first-issue` (Phase 1 部分)

---

## 📌 Related

- #XXX - ESLint 配置优化 (已完成)
- #XXX - 测试套件修复 (已完成)
