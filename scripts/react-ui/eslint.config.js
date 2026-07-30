import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'src-tauri']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      'react-hooks': reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.node, // Add node globals for process, etc.
      },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      // Keep the established Hooks checks without implicitly enabling the
      // React Compiler rule suite during a dependency security upgrade.
      'react-hooks/rules-of-hooks': 'error',

      // === 放宽 "未使用变量" 规则 ===
      // 允许以 _ 开头的未使用变量（常见约定）
      // 允许以大写字母开头的未使用变量（组件名、常量）
      'no-unused-vars': ['warn', {
        varsIgnorePattern: '^_|^[A-Z]',
        argsIgnorePattern: '^_',
      }],

      // === 放宽 React Hooks 依赖检查 ===
      // 将错误降级为警告，避免阻塞开发
      'react-hooks/exhaustive-deps': 'warn',

      // === 允许 Context 导出非组件 ===
      // Fast Refresh 限制过于严格，改为警告
      'react-refresh/only-export-components': ['warn', {
        allowConstantExport: true,
      }],

      // === 其他优化 ===
      // 允许不必要的转义（正则表达式中常见）
      'no-useless-escape': 'warn',

    },
  },
  {
    files: ['src/**/*.{js,jsx}'],
    rules: {
      // === 前端可维护性门禁 ===
      // 新的生产代码不得超过 600 行。已有超限文件在下方按当前行数
      // 冻结上限：可以缩小，但不得继续膨胀。
      'max-lines': ['error', {
        max: 600,
        skipBlankLines: false,
        skipComments: false,
      }],

      // 先暴露最严重的历史热点，避免低阈值产生无法行动的警告洪水。
      // 随着债务清理逐步降低阈值，再升级为 error。
      'max-lines-per-function': ['warn', {
        max: 500,
        skipBlankLines: true,
        skipComments: true,
        IIFEs: true,
      }],
      'complexity': ['warn', 50],
      'max-statements': ['warn', 150],
    },
  },
  {
    // 测试夹具和声明式配置不受生产代码架构门禁约束。
    files: [
      '**/*.{test,spec}.{js,jsx}',
      '**/__tests__/**/*.{js,jsx}',
      'src/config/**/*.{js,jsx}',
    ],
    rules: {
      'max-lines': 'off',
      'max-lines-per-function': 'off',
      'complexity': 'off',
      'max-statements': 'off',
    },
  },
  {
    // Legacy debt ceilings, captured on 2026-07-30.
    // Never raise these values. Refactors should remove entries as files shrink
    // below the default 600-line production limit.
    files: ['src/components/neologism/JudgmentCourt.jsx'],
    rules: {
      'max-lines': ['error', 1305],
    },
  },
  {
    files: ['src/hooks/useGlossaryActions.js'],
    rules: {
      'max-lines': ['error', 891],
    },
  },
  {
    files: ['src/pages/TaskDetailPage.jsx'],
    rules: {
      'max-lines': ['error', 771],
    },
  },
  {
    files: ['src/components/glossary/GlossaryOverview.jsx'],
    rules: {
      'max-lines': ['error', 727],
    },
  },
  {
    files: ['src/components/glossary/GlossaryOperations.jsx'],
    rules: {
      'max-lines': ['error', 708],
    },
  },
  {
    files: ['src/hooks/useIncrementalTranslation.js'],
    rules: {
      'max-lines': ['error', 690],
    },
  },
  {
    files: ['src/pages/ModelArenaPage.jsx'],
    rules: {
      'max-lines': ['error', 690],
    },
  },
  {
    files: ['src/hooks/useAgentWorkshopController.js'],
    rules: {
      'max-lines': ['error', 659],
    },
  },
  {
    files: ['src/pages/ProjectTrackingPage.jsx'],
    rules: {
      'max-lines': ['error', 609],
    },
  },
])
