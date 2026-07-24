import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { notifications } from '@mantine/notifications';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';

const translate = vi.hoisted(() => (key) => key);

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: translate }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const candidates = [
  {
    id: 1,
    original: 'Hyperlane Relay',
    suggestion: '跃迁中继',
    reasoning: 'Recurring game term',
    context_snippets: [],
    duplicate_matches: [],
  },
  {
    id: 2,
    original: 'Quantum Anchor',
    suggestion: '量子锚点',
    reasoning: 'Recurring game term',
    context_snippets: [],
    duplicate_matches: [],
  },
  {
    id: 3,
    original: 'Void Beacon',
    suggestion: '虚空信标',
    reasoning: 'Recurring game term',
    context_snippets: [],
    duplicate_matches: [],
  },
];

describe('JudgmentCourt batch rejection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] },
        });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({ data: { candidates } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('requires confirmation and removes every successfully rejected term', async () => {
    api.post.mockResolvedValue({ data: { status: 'success' } });
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    fireEvent.click(screen.getByRole('checkbox', { name: 'neologism_review.court.select_all' }));
    fireEvent.click(screen.getByRole('button', { name: 'neologism_review.court.batch_reject' }));

    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', {
      name: 'neologism_review.court.batch_reject_confirm',
    }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledTimes(3);
      expect(screen.queryByRole('button', { name: /Hyperlane Relay/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Quantum Anchor/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Void Beacon/ })).not.toBeInTheDocument();
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.batch_rejected_title',
        color: 'gray',
      }));
    });
  });

  it('keeps failed terms selected when a batch only partially succeeds', async () => {
    api.post.mockImplementation((url) => (
      url.includes('/2/reject')
        ? Promise.reject(new Error('network failure'))
        : Promise.resolve({ data: { status: 'success' } })
    ));
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    fireEvent.click(screen.getByRole('checkbox', { name: 'neologism_review.court.select_all' }));
    fireEvent.click(screen.getByRole('button', { name: 'neologism_review.court.batch_reject' }));
    fireEvent.click(await screen.findByRole('button', {
      name: 'neologism_review.court.batch_reject_confirm',
    }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Hyperlane Relay/ })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Quantum Anchor/ })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Void Beacon/ })).not.toBeInTheDocument();
      expect(screen.getByRole('checkbox', {
        name: 'neologism_review.court.select_candidate',
      })).toBeChecked();
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.batch_partial_title',
        color: 'orange',
      }));
    });
  });
});
