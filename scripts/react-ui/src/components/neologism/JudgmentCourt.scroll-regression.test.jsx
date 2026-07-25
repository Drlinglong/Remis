import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('JudgmentCourt docket scrolling regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] },
        });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({
          data: {
            candidates: Array.from({ length: 20 }, (_, index) => ({
              id: index + 1,
              original: `Candidate ${index + 1}`,
              suggestion: `Translation ${index + 1}`,
              reasoning: 'Recurring game term',
              context_snippets: [],
              duplicate_matches: [],
            })),
          },
        });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('keeps docket controls fixed above one native list scroller', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Candidate 20/ });

    const panel = screen.getByTestId('neologism-docket-panel');
    const listScroller = screen.getByTestId('neologism-docket-scroll');
    const selectAll = screen.getByRole('checkbox', {
      name: 'neologism_review.court.select_all',
    });

    expect(listScroller).toHaveStyle({
      overflowY: 'auto',
      overflowX: 'hidden',
    });
    expect(panel.querySelectorAll('.mantine-ScrollArea-root')).toHaveLength(0);
    expect(within(listScroller).getByRole('button', { name: /Candidate 20/ })).toBeInTheDocument();
    expect(listScroller).not.toContainElement(selectAll);
  });
});
