import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectTrackingPage from '../ProjectTrackingPage';
import projectWatchService from '../../services/projectWatchService';
import projectService from '../../services/projectService';

const navigateMock = vi.fn();

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
    i18n: { language: 'zh' },
  }),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('../../services/projectWatchService', () => ({
  default: {
    listWatches: vi.fn(),
    createWatch: vi.fn(),
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
        last_scan_summary: { changed_count: 2 },
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
    fireEvent.click(screen.getByRole('button', { name: '添加追踪' }));

    fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Steam Workshop Test' } });
    fireEvent.change(screen.getByLabelText('路径'), { target: { value: 'J:/Steam/workshop/test' } });

    expect(screen.getByLabelText('名称')).toHaveValue('Steam Workshop Test');
    expect(screen.getByLabelText('路径')).toHaveValue('J:/Steam/workshop/test');
  });
});
