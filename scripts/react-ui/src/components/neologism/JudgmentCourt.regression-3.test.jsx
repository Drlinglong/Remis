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

describe('JudgmentCourt next-case regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.post.mockResolvedValue({ data: {} });
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

  it('selects the adjacent case after approval instead of jumping to the first', async () => {
    // Regression: ISSUE-004 — approving a case always jumped back to the first docket item.
    // Found by /qa on 2026-07-20
    // Report: .gstack/qa-reports/qa-report-remis-neologism-2026-07-20.md
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    const secondCase = await screen.findByRole('button', { name: /Quantum Anchor/ });
    fireEvent.click(secondCase);
    await waitFor(() => {
      expect(secondCase).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByDisplayValue('量子锚点')).toBeInTheDocument();
    });
    expect(api.post).not.toHaveBeenCalled();
    const approveButton = screen.getByRole('button', { name: /neologism_review.court.approve/ });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/neologisms/2/approve', expect.any(Object));
      expect(screen.queryByRole('button', { name: /Quantum Anchor/ })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Void Beacon/ })).toHaveAttribute('aria-pressed', 'true');
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.approved_title',
        color: 'green',
        withBorder: true,
        autoClose: 3200,
      }));
    });

    expect(screen.getByRole('button', { name: /Hyperlane Relay/ })).toHaveAttribute('aria-pressed', 'false');
  });

  it('shows explicit transient confirmation after rejecting a term', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    fireEvent.click(screen.getByRole('button', { name: /neologism_review.court.ignore/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/neologisms/1/reject', {
        project_id: 'project-1',
      });
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.rejected_title',
        color: 'gray',
        withBorder: true,
        autoClose: 3200,
      }));
    });
  });
});
