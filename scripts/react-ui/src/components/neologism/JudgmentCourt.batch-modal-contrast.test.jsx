import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';
import styles from './JudgmentCourt.module.css';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const candidates = [{
  id: 1,
  original: 'Hyperlane Relay',
  suggestion: '跃迁中继',
  reasoning: 'Recurring game term',
  context_snippets: [],
  duplicate_matches: [],
}];

describe('JudgmentCourt batch modal contrast', () => {
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

  async function selectCandidate() {
    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    fireEvent.click(screen.getByRole('checkbox', {
      name: 'neologism_review.court.select_all',
    }));
  }

  it.each([
    {
      open: 'neologism_review.court.batch_approve',
      title: 'neologism_review.court.batch_approve_confirm_title',
      confirm: 'neologism_review.court.batch_approve_confirm',
      action: 'paper-primary',
    },
    {
      open: 'neologism_review.court.batch_reject',
      title: 'neologism_review.court.batch_reject_confirm_title',
      confirm: 'neologism_review.court.batch_reject_confirm',
      action: 'paper-danger',
    },
  ])('gives the $open dialog a readable paper contract', async ({
    open,
    title,
    confirm,
    action,
  }) => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await selectCandidate();
    fireEvent.click(screen.getByRole('button', { name: open }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveClass(styles.batchModalContent);
    expect(screen.getByText(title)).toHaveClass(styles.batchModalTitle);
    expect(within(dialog).getByRole('alert')).toHaveClass(styles.batchModalAlert);
    expect(within(dialog).getByRole('button', {
      name: 'neologism_review.court.batch_cancel',
    })).toHaveAttribute('data-remis-action', 'paper-secondary');
    expect(within(dialog).getByRole('button', { name: confirm })).toHaveAttribute(
      'data-remis-action',
      action,
    );
  });
});
