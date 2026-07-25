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
    original: 'Galactic Republic',
    suggestion: '银河共和国',
    reasoning: 'An existing glossary entry matches this source term.',
    context_snippets: [],
    duplicate_matches: [{
      entry_id: 'existing-1',
      source_term: 'Galactic Republic',
      glossary_name: 'Project Glossary',
    }],
  },
  {
    id: 2,
    original: 'Quantum Anchor',
    suggestion: '量子锚点',
    reasoning: 'Use the established setting-specific rendering.',
    context_snippets: [],
    duplicate_matches: [],
  },
];

describe('JudgmentCourt duplicate explanation regression', () => {
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

  it('shows one structured duplicate explanation and keeps AI advice for new terms', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Galactic Republic/ });

    expect(screen.getByText('neologism_review.court.duplicate_warning_title')).toBeInTheDocument();
    expect(screen.queryByTestId('neologism-analysis-panel')).not.toBeInTheDocument();
    expect(screen.queryByText(candidates[0].reasoning)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Quantum Anchor/ }));

    expect(screen.queryByText('neologism_review.court.duplicate_warning_title')).not.toBeInTheDocument();
    expect(screen.getByTestId('neologism-analysis-panel')).toHaveAttribute(
      'data-remis-surface',
      'paper',
    );
    expect(screen.getByText(candidates[1].reasoning)).toBeInTheDocument();
  });
});
