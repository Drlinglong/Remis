import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectPathManager from './ProjectPathManager';
import api from '../../utils/api';
import { open } from '@tauri-apps/plugin-dialog';

vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Modal: ({ opened, children, title }) =>
      opened ? (
        <div>
          <div>{title}</div>
          {children}
        </div>
      ) : null,
  };
});

const { MantineProvider } = await import('@mantine/core');

vi.mock('../../utils/api', () => ({
  default: {
    post: vi.fn(),
  },
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

const renderWithProvider = (ui) =>
  render(<MantineProvider>{ui}</MantineProvider>);

describe('ProjectPathManager', () => {
  const projectDetails = {
    project_id: 'proj-1',
    source_path: 'C:/mods/source',
    translation_dirs: ['C:/mods/old-translation'],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.post.mockResolvedValue({ data: { ok: true } });
    open.mockResolvedValue('C:/mods/new-translation');
  });

  it('adds a browsed translation directory and saves it', async () => {
    const onPathsUpdated = vi.fn();

    renderWithProvider(
      <ProjectPathManager
        projectDetails={projectDetails}
        onPathsUpdated={onPathsUpdated}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths_button' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.browse' }));

    await waitFor(() => {
      expect(open).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.add' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.save' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/project/proj-1/config', {
        translation_dirs: ['C:/mods/old-translation', 'C:/mods/new-translation'],
      });
    });

    expect(onPathsUpdated).toHaveBeenCalledOnce();
  });

  it('does not duplicate an existing translation directory', async () => {
    open.mockResolvedValue('C:/mods/old-translation');

    renderWithProvider(<ProjectPathManager projectDetails={projectDetails} />);

    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths_button' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.browse' }));

    await waitFor(() => {
      expect(open).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.add' }));
    fireEvent.click(screen.getByRole('button', { name: 'project_management.manage_paths.save' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/project/proj-1/config', {
        translation_dirs: ['C:/mods/old-translation'],
      });
    });
  });
});
