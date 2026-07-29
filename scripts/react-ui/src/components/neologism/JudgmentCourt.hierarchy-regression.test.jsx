import React from 'react';
import { render, screen } from '@testing-library/react';
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

describe('JudgmentCourt visual hierarchy regression', () => {
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
            candidates: [{
              id: 1,
              original: 'Hyperlane Relay',
              suggestion: '跃迁中继',
              reasoning: 'Recurring game term',
              context_evidence: [{
                snippet: 'Hyperlane Relay activates.',
                source_file: 'events/relay_events.yml',
              }],
              duplicate_matches: [],
            }],
          },
        });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('makes approval primary while keeping rejection visibly secondary', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });

    expect(screen.getByTestId('neologism-approve-action')).toHaveAttribute('data-variant', 'filled');
    expect(screen.getByTestId('neologism-reject-action')).toHaveAttribute('data-variant', 'subtle');
    expect(screen.getByTestId('neologism-candidate-anchor')).toHaveAttribute(
      'data-visual-priority',
      'primary',
    );
    expect(screen.getByTestId('neologism-analysis-panel')).toHaveAttribute(
      'data-visual-priority',
      'secondary',
    );
    expect(screen.getByTestId('neologism-decision-panel')).toHaveAttribute(
      'data-visual-priority',
      'action',
    );
  });
});
