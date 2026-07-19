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

describe('JudgmentCourt translation draft regression', () => {
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

  it('keeps a candidate draft while the reviewer checks another case', async () => {
    // Regression: ISSUE-003 — switching candidates silently discarded edited translations.
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
    const translation = screen.getByDisplayValue('跃迁中继');

    fireEvent.change(translation, { target: { value: '自定义跃迁中继' } });
    fireEvent.click(secondCase);
    fireEvent.click(firstCase);

    expect(screen.getByDisplayValue('自定义跃迁中继')).toBeInTheDocument();
  });
});
