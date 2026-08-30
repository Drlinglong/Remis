import React from 'react';
import { Box } from '@mantine/core';

import HomeDashboardView from '../pages/home/HomeDashboardView';
import styles from './HomeDashboardVisualFixture.module.css';

const translations = {
  button_refresh: '刷新',
  homepage_action_continue_project: '继续项目',
  homepage_dashboard_error: '项目组合数据暂时无法读取。',
  homepage_live_work_empty: '当有翻译、校对或待确认任务时，它们会在这里成为你的下一步。',
  homepage_live_work_subtitle: '先处理最需要你注意的任务，其他信息保持安静。',
  homepage_live_work_title: '当前工作',
  homepage_project_portfolio: '项目组合概览',
  homepage_recent_activity_unavailable: '连接恢复后才能读取最近活动。',
  homepage_stat_active_projects: '活跃项目',
  homepage_stat_completion_rate: '完成率',
  homepage_stat_total_projects: '项目总数',
  homepage_workspace_eyebrow: 'Remis 工作区',
  homepage_workspace_subtitle: '把待处理任务、项目状态和最近活动放在同一个可扫读的主界面。',
  'task_center.attention_summary': '{{count}} 个任务需要你检查',
  'task_center.empty_title': '目前没有待处理任务',
  'task_center.retry': '重试',
  'task_center.view_history': '任务历史',
  'task_center.view_task': '打开优先任务',
};

const fixtureT = (key, options = {}) => {
  const template = translations[key] || options.defaultValue || key;
  return String(template).replace(/\{\{(\w+)\}\}/g, (_match, name) => String(options[name] ?? ''));
};

const noop = () => undefined;
const longProjectName = '星港远征：失落航道与群星彼端的超长项目名称验证';
const longTaskId = 'translation-task-2026-08-10-7f3c0d8a4e9b6c2d1a0f-unbroken-identifier';

const activeDashboard = {
  phase: 'ready',
  error: null,
  refresh: noop,
  data: {
    stats: { total_projects: 12, active_projects: 4, completion_rate: 68 },
    charts: {
      project_status: [
        { name: 'todo', value: 4 },
        { name: 'in_progress', value: 3 },
        { name: 'proofreading', value: 2 },
        { name: 'done', value: 7 },
      ],
      project_distribution: [
        { name: 'stellaris', value: 5 },
        { name: 'victoria3', value: 4 },
        { name: 'hoi4', value: 3 },
      ],
    },
    recentActivity: [
      {
        id: 'activity-long-path',
        type: 'path_registered',
        title: `C:\\Users\\Drlin\\Documents\\Remis\\${longProjectName}\\localisation\\simp_chinese\\events_l_simp_chinese.yml`,
        description: 'Auto-registered translation output path',
        timestamp: '2026-08-10T10:30:00Z',
      },
      {
        id: 'activity-translation',
        type: 'translate',
        title: '已生成增量翻译草稿',
        description: 'Build incremental update (fixture)',
        timestamp: '2026-08-10T09:15:00Z',
      },
    ],
  },
};

const activeTasks = [
  {
    task_id: longTaskId,
    kind: `visual_fixture_${longTaskId}`,
    title: `${longProjectName} — 等待检查增量翻译结果`,
    status: 'awaiting_approval',
    progress: 82,
    blocking: true,
    created_at: '2026-08-10T08:00:00Z',
    started_at: '2026-08-10T08:05:00Z',
    attention_reason: '检查模型修复建议后再批准下一阶段。',
    created_by: { type: 'agent', label: 'Remis Agent' },
    allowed_actions: [],
  },
  {
    task_id: 'proofreading-task-fixture',
    kind: 'proofreading',
    title: '人工校对：事件链与专名一致性',
    status: 'running',
    progress: 46,
    blocking: false,
    created_at: '2026-08-10T07:00:00Z',
    started_at: '2026-08-10T07:10:00Z',
    created_by: { type: 'user', label: '人工工作流' },
    allowed_actions: [],
  },
  {
    task_id: 'completed-task-fixture',
    kind: 'context_analysis',
    title: '上下文档案分析已完成',
    status: 'completed',
    progress: 100,
    blocking: false,
    created_at: '2026-08-09T12:00:00Z',
    started_at: '2026-08-09T12:05:00Z',
    completed_at: '2026-08-09T12:45:00Z',
    created_by: { type: 'agent', label: 'Remis Agent' },
    allowed_actions: ['archive_task'],
  },
];

const activeWorkflow = {
  attentionCount: 2,
  handleError: '',
  handleErrorTaskId: '',
  handlingTaskId: '',
  markHandled: noop,
  openProjectManagement: noop,
  openTask: noop,
  openTaskHistory: noop,
  primaryTask: activeTasks[0],
  refreshLiveWork: noop,
  tasksLoading: false,
  visibleTasks: activeTasks,
};

const emptyDashboard = {
  phase: 'error',
  error: new Error('项目组合服务暂时离线；当前任务区仍然可用。'),
  refresh: noop,
  data: {
    stats: { total_projects: null, active_projects: null, completion_rate: null },
    charts: { project_status: [], project_distribution: [] },
    recentActivity: [],
  },
};

const emptyWorkflow = {
  ...activeWorkflow,
  attentionCount: 0,
  primaryTask: null,
  visibleTasks: [],
};

export default function HomeDashboardVisualFixture({ scenario = 'active-partial', themeId }) {
  const active = scenario === 'active-partial';

  return (
    <Box
      className={styles.scrollOwner}
      data-remis-scroll-owner="main-content"
      data-testid={`home-dashboard-${scenario}`}
      data-theme-id={themeId}
      data-visual-ready="true"
    >
      <HomeDashboardView
        dashboard={active ? activeDashboard : emptyDashboard}
        greeting={active ? '下午好，玲珑' : '回到工作区'}
        liveWork={active ? activeWorkflow : emptyWorkflow}
        t={fixtureT}
      />
    </Box>
  );
}
