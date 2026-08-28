import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectHistory from './ProjectHistory';
import api from '../../utils/api';

const navigateMock = vi.fn();

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, fallback) => typeof fallback === 'string' ? fallback : key,
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
      exists: () => false,
    },
  }),
}));

describe('ProjectHistory payload boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderHistory = () => render(
    <MantineProvider>
      <ProjectHistory projectId="project-1" />
    </MantineProvider>,
  );

  it('renders history from a common wrapper and ignores malformed records', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        data: {
          history: [
            null,
            'malformed-history-record',
            {},
            { history_id: 'missing-action', description: 'Malformed history' },
            {
              history_id: 'history-1',
              action_type: 'import',
              description: 'Imported project',
              timestamp: '2026-08-28T00:00:00Z',
            },
          ],
        },
      },
    });

    renderHistory();

    expect(await screen.findByText('Imported project')).toBeInTheDocument();
    expect(screen.getByText('IMPORT')).toBeInTheDocument();
    expect(screen.queryByText('Malformed history')).not.toBeInTheDocument();
  });

  it('shows the empty state for a null history response', async () => {
    api.get.mockResolvedValueOnce({ data: null });

    renderHistory();

    expect(await screen.findByText('No history yet')).toBeInTheDocument();
  });
});
