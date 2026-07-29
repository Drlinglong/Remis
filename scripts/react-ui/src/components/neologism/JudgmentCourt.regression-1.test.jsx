import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
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
];

describe('JudgmentCourt candidate accessibility regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo', game_id: 'stellaris' }] },
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

  it('renders every docket case as a native selectable button', async () => {
    // Regression: ISSUE-002 — docket cards could not receive keyboard focus.
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

    const firstCase = await screen.findByRole('button', { name: /Hyperlane Relay/ });
    const secondCase = screen.getByRole('button', { name: /Quantum Anchor/ });

    expect(firstCase.tagName).toBe('BUTTON');
    expect(firstCase).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(secondCase);

    expect(secondCase).toHaveAttribute('aria-pressed', 'true');
    expect(firstCase).toHaveAttribute('aria-pressed', 'false');
  });

  it('keeps project context and review controls in a compact workspace', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });

    expect(screen.getByTestId('neologism-project-toolbar')).toBeInTheDocument();
    expect(screen.getByRole('textbox', {
      name: 'neologism_review.court.current_project',
    })).toHaveValue('Stellaris Demo');
    expect(screen.queryByRole('heading', { name: 'Stellaris Demo' })).not.toBeInTheDocument();
    expect(screen.getByTestId('neologism-review-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('neologism-decision-panel')).toBeInTheDocument();
  });

  it('opens the bound project glossary from the prominent context card', async () => {
    const onOpenGlossary = vi.fn();
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
          onOpenGlossary={onOpenGlossary}
        />
      </MantineProvider>,
    );

    const openButton = await screen.findByRole('button', {
      name: 'neologism_review.court.inspect_project_glossary',
    });
    fireEvent.click(openButton);

    expect(onOpenGlossary).toHaveBeenCalledWith({
      glossaryId: 3,
      gameId: 'stellaris',
    });
  });
});
