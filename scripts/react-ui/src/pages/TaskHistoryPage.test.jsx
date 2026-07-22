import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TaskHistoryPage from './TaskHistoryPage';
import api from '../utils/api';
import { taskDayBounds } from '../utils/taskDates';

const navigateMock = vi.fn();
const translateMock = (key, options) => {
  if (key === 'task_center.kind.initial_translation') return 'Initial translation';
  return options?.defaultValue || key;
};

vi.mock('../utils/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translateMock,
    i18n: { language: 'en' },
  }),
}));

const { MantineProvider } = await import('@mantine/core');

describe('TaskHistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({
      data: {
        total_count: 1,
        tasks: [{
          task_id: 'historical-task',
          kind: 'initial_translation',
          title: 'Translation from this morning',
          status: 'failed',
          created_at: '2026-07-22T01:00:00Z',
          finished_at: '2026-07-22T01:00:08Z',
          created_by: { type: 'user', label: 'User' },
          archived_at: '2026-07-22T02:00:00Z',
        }],
      },
    });
  });

  it('loads all logs for the selected local day and opens the exact task', async () => {
    const now = new Date();
    const expectedDate = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
    ].join('-');
    const bounds = taskDayBounds(expectedDate);
    render(<MantineProvider><TaskHistoryPage /></MantineProvider>);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/tasks', {
        params: {
          include_archived: true,
          from_time: bounds.fromTime,
          to_time: bounds.toTime,
          offset: 0,
          limit: 100,
        },
      });
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Initial translation' }));
    expect(navigateMock).toHaveBeenCalledWith('/tasks/historical-task');
    expect(screen.getByText('task_history.handled')).toBeInTheDocument();
  });
});
