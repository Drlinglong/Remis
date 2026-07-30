import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TaskHistoryPage from './TaskHistoryPage';
import api from '../utils/api';

vi.mock('../utils/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('react-router', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({ setPageContext: vi.fn() }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => (
      key === 'task_center.kind.model_arena'
        ? '模型竞技场试译'
        : (options?.defaultValue || key)
    ),
    i18n: { language: 'zh' },
  }),
}));

const { MantineProvider } = await import('@mantine/core');

describe('TaskHistoryPage model arena localization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({
      data: {
        total_count: 1,
        tasks: [{
          task_id: 'arena-task',
          kind: 'model_arena',
          title: 'Run model arena',
          status: 'completed',
          created_at: '2026-07-29T09:32:24Z',
          finished_at: '2026-07-29T09:33:48Z',
          created_by: { type: 'user', label: '用户' },
        }],
      },
    });
  });

  it('does not expose the backend English title as a secondary label', async () => {
    render(<MantineProvider><TaskHistoryPage /></MantineProvider>);

    expect(await screen.findByText('模型竞技场试译')).toBeInTheDocument();
    expect(screen.queryByText('Run model arena')).not.toBeInTheDocument();
  });
});
