import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ArchivesPage from './ArchivesPage';
import api from '../utils/api';

const navigateMock = vi.fn();

vi.mock('../utils/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}));

describe('ArchivesPage payload boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderPage = () => render(
    <MantineProvider>
      <ArchivesPage />
    </MantineProvider>,
  );

  it('renders archives returned in a common response wrapper', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        data: {
          archives: [
            { project_id: 'missing-name' },
            {
              project_id: 'archived-project',
              name: 'Archived project',
              game_id: 'victoria3',
              source_path: 'mods/archive',
              status: 'archived',
            },
          ],
        },
      },
    });

    renderPage();

    expect(await screen.findByText('Archived project')).toBeInTheDocument();
    expect(screen.getByText('archived')).toBeInTheDocument();
    expect(screen.queryByText('missing-name')).not.toBeInTheDocument();
  });

  it('treats a null archive response as an empty collection', async () => {
    api.get.mockResolvedValueOnce({ data: null });

    renderPage();

    await waitFor(() => expect(screen.getByText('The archives are empty.')).toBeInTheDocument());
    expect(screen.queryByText('Archived project')).not.toBeInTheDocument();
  });
});
