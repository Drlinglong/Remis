import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectTrackingPage from '../ProjectTrackingPage';
import projectWatchService from '../../services/projectWatchService';
import projectService from '../../services/projectService';

const navigateMock = vi.fn();
const setPageContextMock = vi.fn();

const zhTranslations = {
  'project_tracking.title': '项目追踪',
  'project_tracking.subtitle': '给 Remis 添加需要持续监控的 Mod 本地路径，并在本地化文件发生变化后，一键跳转到增量更新。',
  'project_tracking.add_new_project': '添加需要追踪的新项目',
  'project_tracking.edit': '编辑需要追踪的项目',
  'project_tracking.scan_selected': '扫描选中项',
  'project_tracking.refresh': '刷新',
  'project_tracking.empty': '还没有需要追踪的项目路径。',
  'project_tracking.path': '路径',
  'project_tracking.path_description': '把这个路径设置为你需要持续监控更新的 mod 在本地磁盘上的存放地址，例如 SteamLibrary\\steamapps\\workshop\\content\\游戏ID\\创意工坊物品ID。Remis 可以监控该文件夹中所有本地化文件的改动，并在出现改动时提示你。',
  'project_tracking.path_safety_description': 'Remis 不会修改或者删除该文件夹中的任何文件。',
  'project_tracking.project': '关联项目',
  'project_tracking.project_description': '选择这个 mod 在 Remis 内对应的翻译项目。',
  'project_tracking.status': '状态',
  'project_tracking.last_scan': '最后扫描',
  'project_tracking.changes': '变更',
  'project_tracking.interval': '扫描间隔',
  'project_tracking.interval_unit': '单位',
  'project_tracking.actions': '操作',
  'project_tracking.name': '名称',
  'project_tracking.enabled': '启用定时扫描',
  'project_tracking.enabled_description': '只要 Remis 处在运行状态，就会隔一定时间扫描本项目，检查是否有更新。',
  'project_tracking.unit_minutes': '分钟',
  'project_tracking.unit_hours': '小时',
  'project_tracking.unit_days': '天',
  'project_tracking.save': '保存',
  'project_tracking.cancel': '取消',
  'project_tracking.browse': '浏览',
  'project_tracking.unlinked': '未关联',
  'project_tracking.start_incremental': '开始增量更新',
  'project_tracking.status_baseline': '已建立基线',
  'project_tracking.status_clean': '无变更',
  'project_tracking.status_changed': '有变更',
  'project_tracking.status_never': '未扫描',
  'project_tracking.status_no_localization': '没有本地化文件',
  'project_tracking.scanned_files': '已扫描文件',
  'project_tracking.scan_result': '扫描完成',
  'project_tracking.scan_message': '扫描完成：{{status}}，已扫描文件 {{scanned}}，变更 {{changes}}。{{path}}',
  'project_tracking.scan_now': '扫描',
  'project_tracking.delete': '删除',
  'project_tracking.select_project_first': '这个追踪项还没有关联 Remis 项目，无法跳转到增量更新。',
};

vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Modal: ({ opened, title, children }) => opened ? (
      <div role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values = {}) => {
      let text = zhTranslations[key] || key;
      Object.entries(values).forEach(([name, value]) => {
        text = text.replace(`{{${name}}}`, value);
      });
      return text;
    },
  }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    setPageContext: setPageContextMock,
  }),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('../../services/projectWatchService', () => ({
  default: {
    listWatches: vi.fn(),
    createWatch: vi.fn(),
    updateWatch: vi.fn(),
    scanWatches: vi.fn(),
    deleteWatch: vi.fn(),
  },
}));

vi.mock('../../services/projectService', () => ({
  default: {
    getActiveProjects: vi.fn(),
  },
}));

const renderWithProvider = (ui) => render(
  <MantineProvider>
    <MemoryRouter>{ui}</MemoryRouter>
  </MantineProvider>,
);

describe('ProjectTrackingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectService.getActiveProjects.mockResolvedValue({
      data: [{ project_id: 'p1', name: 'Vic3 Demo', game_id: 'victoria3', source_path: 'J:/old' }],
    });
    projectWatchService.listWatches.mockResolvedValue({
      data: [{
        watch_id: 'w1',
        name: 'Steam Vic3',
        path: 'J:/Steam/workshop/demo',
        project_id: 'p1',
        enabled: true,
        scan_interval_minutes: 30,
        status: 'changed',
        last_scan_at: '2026-06-10T00:00:00+00:00',
        last_scan_summary: { changed_count: 2, task_id: 'scan-task-1' },
      }],
    });
    projectWatchService.scanWatches.mockResolvedValue({ data: [] });
    projectWatchService.createWatch.mockResolvedValue({ data: {} });
  });

  it('renders watched paths and jumps to incremental update with project and source path', async () => {
    renderWithProvider(<ProjectTrackingPage />);

    expect(await screen.findByText('项目追踪')).toBeInTheDocument();
    expect(screen.getByText('Steam Vic3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('开始增量更新'));

    expect(navigateMock).toHaveBeenCalledWith('/incremental-translation', {
      state: {
        projectId: 'p1',
        customSourcePath: 'J:/Steam/workshop/demo',
        fromProjectWatch: true,
      },
    });
  });

  it('opens the exact scheduled scan result from the watched project row', async () => {
    renderWithProvider(<ProjectTrackingPage />);

    await screen.findByText('Steam Vic3');
    fireEvent.click(screen.getByLabelText('task_center.view_task'));

    expect(navigateMock).toHaveBeenCalledWith('/tasks/scan-task-1');
  });

  it('scans selected watches', async () => {
    renderWithProvider(<ProjectTrackingPage />);

    await screen.findByText('Steam Vic3');
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByRole('button', { name: '扫描选中项' }));

    await waitFor(() => {
      expect(projectWatchService.scanWatches).toHaveBeenCalledWith(['w1']);
    });
  });

  it('keeps the add-watch form stable while typing text fields', async () => {
    renderWithProvider(<ProjectTrackingPage />);

    await screen.findByText('Steam Vic3');
    fireEvent.click(screen.getByRole('button', { name: '添加需要追踪的新项目' }));

    fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Steam Workshop Test' } });
    fireEvent.change(screen.getByLabelText('路径'), { target: { value: 'J:/Steam/workshop/test' } });

    expect(screen.getByLabelText('名称')).toHaveValue('Steam Workshop Test');
    expect(screen.getByLabelText('路径')).toHaveValue('J:/Steam/workshop/test');
  });

  it('shows schedule interval only when scheduled scanning is enabled', async () => {
    renderWithProvider(<ProjectTrackingPage />);

    await screen.findByText('Steam Vic3');
    fireEvent.click(screen.getByRole('button', { name: '添加需要追踪的新项目' }));

    const dialog = screen.getByRole('dialog', { name: '添加需要追踪的新项目' });
    expect(within(dialog).getByText('扫描间隔')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('switch'));

    expect(within(dialog).queryByText('扫描间隔')).not.toBeInTheDocument();
  });

  it('blocks incremental update when a watched path is not linked to a project', async () => {
    projectWatchService.listWatches.mockResolvedValueOnce({
      data: [{
        watch_id: 'w-unlinked',
        name: 'Loose Workshop Folder',
        path: 'J:/Steam/workshop/loose',
        project_id: null,
        enabled: true,
        scan_interval_minutes: 30,
        status: 'changed',
        last_scan_at: null,
        last_scan_summary: { changed_count: 1 },
      }],
    });

    renderWithProvider(<ProjectTrackingPage />);

    expect(await screen.findByText('Loose Workshop Folder')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('开始增量更新'));

    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByText('这个追踪项还没有关联 Remis 项目，无法跳转到增量更新。')).toBeInTheDocument();
  });

  it('preserves day-based schedule intervals when editing a watched path', async () => {
    projectWatchService.listWatches.mockResolvedValueOnce({
      data: [{
        watch_id: 'w-days',
        name: 'Weekly Workshop Folder',
        path: 'J:/Steam/workshop/weekly',
        project_id: 'p1',
        enabled: true,
        scan_interval_minutes: 2880,
        status: 'clean',
        last_scan_at: null,
        last_scan_summary: { changed_count: 0 },
      }],
    });
    projectWatchService.updateWatch.mockResolvedValue({ data: {} });

    renderWithProvider(<ProjectTrackingPage />);

    expect(await screen.findByText('Weekly Workshop Folder')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('编辑需要追踪的项目'));
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(projectWatchService.updateWatch).toHaveBeenCalledWith('w-days', expect.objectContaining({
        name: 'Weekly Workshop Folder',
        path: 'J:/Steam/workshop/weekly',
        project_id: 'p1',
        enabled: true,
        scan_interval_minutes: 2880,
      }));
    });
  });
});
