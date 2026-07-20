import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
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

describe('JudgmentCourt empty-state regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] },
        });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({ data: { candidates: [] } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('offers a clear route back to mining when the docket is empty', async () => {
    // Regression: ISSUE-005 — an empty docket told the user to select a case
    // even though no case existed.
    // Found by /qa on 2026-07-20
    // Report: .gstack/qa-reports/qa-report-remis-neologism-2026-07-20.md
    const onOpenMining = vi.fn();

    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
          onOpenMining={onOpenMining}
        />
      </MantineProvider>,
    );

    const miningButton = await screen.findByRole('button', {
      name: 'neologism_review.tab_mining',
    });
    expect(screen.getAllByText('neologism_review.court.caught_up')).toHaveLength(2);
    expect(screen.queryByText('neologism_review.court.select_case')).not.toBeInTheDocument();

    fireEvent.click(miningButton);

    expect(onOpenMining).toHaveBeenCalledTimes(1);
  });
});
