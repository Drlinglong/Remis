import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TaskDetailPage from './TaskDetailPage';
import api from '../utils/api';

const translateMock = (key) => key;

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useParams: () => ({ taskId: 'repair-batch-2' }),
}));

vi.mock('../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => ({
    openTaskCenter: vi.fn(),
    refreshTasks: vi.fn(),
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translateMock,
    i18n: { language: 'zh' },
  }),
}));

const { MantineProvider } = await import('@mantine/core');

describe('Task Detail Format Repair result presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({
      data: {
        task_id: 'repair-batch-2',
        parent_task_id: 'repair-parent',
        kind: 'agent_workshop_batch',
        title: 'Format Repair batch',
        status: 'partial_failed',
        progress: 100,
        created_by: { type: 'user', label: 'User' },
        created_at: '2026-07-26T00:00:00Z',
        started_at: '2026-07-26T00:00:01Z',
        finished_at: '2026-07-26T00:00:09Z',
        project_id: 'project-demo',
        project_context: { name: 'Demo project', game_id: 'vic3' },
        summary: { successCount: 2, failedCount: 1 },
        result: {
          summary: '2 fixed, 1 still require review.',
          metadata: {
            batch_number: 2,
            results: [
              {
                file_name: 'events/demo_l_simp_chinese.yml',
                key: 'fixed.entry',
                status: 'SUCCESS',
                parity_message: 'Validation passed',
              },
              {
                file_name: 'events/demo_l_simp_chinese.yml',
                key: 'failed.entry',
                status: 'FAILED',
                parity_message: 'The closing format marker is still missing.',
              },
            ],
          },
        },
        events: [],
        children: [],
        child_aggregate: { total: 0, active: 0, attention: 0, completed: 0, progress: 0 },
        checkpoint: {},
        allowed_actions: ['view_task'],
      },
    });
  });

  it('localizes the aggregate and identifies the exact failed file and key', async () => {
    render(<MantineProvider><TaskDetailPage /></MantineProvider>);

    expect(await screen.findAllByText('task_presentation.result.format_repair_partial')).toHaveLength(2);
    expect(screen.getAllByText('events/demo_l_simp_chinese.yml')).toHaveLength(2);
    expect(screen.getByText('failed.entry')).toBeInTheDocument();
    expect(screen.getByText('task_detail.repair_item_needs_review')).toBeInTheDocument();
    expect(screen.getByText(/The closing format marker is still missing/)).toBeInTheDocument();
    expect(screen.queryByText('2 fixed, 1 still require review.')).not.toBeInTheDocument();
  });
});
