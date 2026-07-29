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

const sourcePath = String.raw`C:\Users\Drlin\AppData\Roaming\RemisModFactoryDev\demo\localisation\english\events.yml`;

describe('JudgmentCourt layout regressions', () => {
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
              source_file: sourcePath,
              context_evidence: [{
                snippet: 'Hyperlane Relay activates.',
                source_file: sourcePath,
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

  it('keeps the complete Windows evidence path readable inside its card', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    const evidenceSource = await screen.findByTestId('neologism-evidence-source');
    const sourceBadge = screen.getByText('events.yml');

    expect(evidenceSource).toHaveTextContent(sourcePath);
    expect(evidenceSource).toHaveStyle({
      whiteSpace: 'normal',
      overflowWrap: 'anywhere',
      wordBreak: 'break-word',
    });
    expect(sourceBadge.closest('[title]')).toHaveAttribute('title', sourcePath);
  });
});
