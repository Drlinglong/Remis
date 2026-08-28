import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectSidebar from './ProjectSidebar';
import api from '../../utils/api';

const setSidebarContent = vi.fn();

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('../../context/SidebarContextCore', () => ({
  useSidebar: () => ({ setSidebarContent }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

describe('ProjectSidebar payload boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderSidebar = () => render(
    <MantineProvider>
      <ProjectSidebar projectId="project-1" onDeleteNote={vi.fn()} />
    </MantineProvider>,
  );

  it('renders wrapped notes while ignoring malformed records', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        payload: {
          notes: [
            null,
            'invalid-note',
            { content: 'Missing identifier' },
            { id: 'note-1', content: 'Persisted project note' },
          ],
        },
      },
    });

    renderSidebar();

    expect(await screen.findByText('Persisted project note')).toBeInTheDocument();
    expect(screen.queryByText('Missing identifier')).not.toBeInTheDocument();
  });

  it('shows the empty state for a null notes response', async () => {
    api.get.mockResolvedValueOnce({ data: null });

    renderSidebar();

    expect(await screen.findByText('project_management.notes_history_title')).toBeInTheDocument();
    expect(screen.getByText('No notes recorded yet.')).toBeInTheDocument();
  });
});
