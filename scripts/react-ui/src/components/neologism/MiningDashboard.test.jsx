import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import MiningDashboard from './MiningDashboard';


vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, fallback) => fallback || key }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.close = vi.fn();
    FakeWebSocket.instances.push(this);
  }
}

const renderDashboard = () => render(
  <MantineProvider>
    <MiningDashboard
      selectedProject="project-1"
      onSelectedProjectChange={vi.fn()}
      onMiningComplete={vi.fn()}
    />
  </MantineProvider>,
);

describe('MiningDashboard', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    global.WebSocket = FakeWebSocket;
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({ data: [{ project_id: 'project-1', name: 'Stellaris Demo' }] });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          data: {
            languages: {},
            api_providers: [{
              value: 'lm_studio',
              label: 'LM Studio',
              default_model: 'local-model',
              available_models: ['local-model'],
            }],
          },
        });
      }
      if (url === '/api/neologisms/mining-files/project-1') {
        return Promise.resolve({ data: [{ file_path: 'events.yml', relative_path: 'events.yml' }] });
      }
      if (url === '/api/neologisms/status/project-1') {
        return Promise.resolve({ data: { status: 'idle' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
    api.post.mockResolvedValue({ data: { task_id: 'task-1', total_files: 3 } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a backend terminal failure delivered by websocket', async () => {
    renderDashboard();

    const startButton = await screen.findByRole('button', { name: 'neologism_review.mining.start_mining' });
    fireEvent.click(startButton);

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(screen.getByText('0 / 3')).toBeInTheDocument();

    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe('ws://127.0.0.1:1453/api/ws/status/task-1');
    act(() => {
      socket.onmessage({
        data: JSON.stringify({
          status: 'failed',
          progress: { current: 1, total: 3 },
          summary: { error: 'schema failed' },
        }),
      });
    });

    expect(await screen.findByText('schema failed')).toBeInTheDocument();
    expect(startButton).toBeEnabled();
    expect(api.get).toHaveBeenCalledWith('/api/neologisms/status/project-1');
    expect(api.get.mock.calls.filter(([url]) => url === '/api/neologisms/status/project-1')).toHaveLength(1);
  });

  it('uses a scoped localized model label', async () => {
    renderDashboard();

    expect(await screen.findByText('neologism_review.mining.model')).toBeInTheDocument();
    expect(screen.queryByText('form_label_model')).not.toBeInTheDocument();
  });
});
