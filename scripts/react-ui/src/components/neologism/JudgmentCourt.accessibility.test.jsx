import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
    original: 'Alpha Relay',
    suggestion: '阿尔法中继',
    reasoning: 'First case',
    context_evidence: [],
    duplicate_matches: [],
  },
  {
    id: 2,
    original: 'Beta Anchor',
    suggestion: '贝塔锚点',
    reasoning: 'Second case',
    context_evidence: [],
    duplicate_matches: [],
  },
];

describe('JudgmentCourt action focus continuity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({ data: { projects: [{ project_id: 'project-1', name: 'Demo' }] } });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({ data: { candidates } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
    api.post.mockResolvedValue({ data: { status: 'success' } });
  });

  it('focuses the adjacent case after approving the current case', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt selectedProject="project-1" onSelectedProjectChange={vi.fn()} />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Alpha Relay/ });
    const approveAction = screen.getByTestId('neologism-approve-action');
    expect(approveAction).toBeEnabled();
    fireEvent.click(approveAction);

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Alpha Relay/ })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Beta Anchor/ })).toHaveFocus();
    });
  });

  it('exposes processing state without replacing the active workspace', async () => {
    let resolvePost;
    api.post.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));

    render(
      <MantineProvider>
        <JudgmentCourt selectedProject="project-1" onSelectedProjectChange={vi.fn()} />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Alpha Relay/ });
    fireEvent.click(screen.getByTestId('neologism-approve-action'));
    expect(screen.getByTestId('neologism-review-workspace')).toHaveAttribute('aria-busy', 'true');

    await act(async () => {
      resolvePost({ data: { status: 'success' } });
    });
    await waitFor(() => {
      expect(screen.getByTestId('neologism-review-workspace')).toHaveAttribute('aria-busy', 'false');
    });
  });
});
