import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReferenceLibraryMaintenanceCard from './ReferenceLibraryMaintenanceCard';
import translationService from '../../services/translationService';
import { referenceLibraryTaskIsActive } from '../../hooks/useReferenceLibraryMaintenance';

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));
vi.mock('../../services/translationService', () => ({
  default: {
    getReferenceLibraryStatus: vi.fn(),
    getActiveReferenceLibraryJob: vi.fn(),
    getReferenceLibraryJob: vi.fn(),
    discoverReferenceLibraries: vi.fn(),
    startReferenceLibraryJob: vi.fn(),
    deleteReferenceLibrary: vi.fn(),
  },
}));

const status = {
  libraries: [{
    game_id: 'victoria3',
    game_name: 'Victoria 3',
    available: true,
    stale: false,
    game_version: '1.9.8',
    entry_count: 42,
    root_path: 'I:/SteamLibrary/steamapps/common/Victoria 3/game/localization',
  }],
};

const t = (key, values) => values ? `${key}:${JSON.stringify(values)}` : key;

describe('ReferenceLibraryMaintenanceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translationService.getReferenceLibraryStatus.mockResolvedValue({ data: status });
    translationService.getActiveReferenceLibraryJob.mockRejectedValue({ response: { status: 404 } });
    translationService.discoverReferenceLibraries.mockResolvedValue({
      data: {
        candidates: [{
          game_id: 'victoria3',
          game_name: 'Victoria 3',
          localization_path: status.libraries[0].root_path,
          status: 'stale',
        }],
      },
    });
    translationService.startReferenceLibraryJob.mockResolvedValue({
      data: { task_id: 'task-1', status: 'queued', progress: {} },
    });
    translationService.getReferenceLibraryJob.mockResolvedValue({
      data: { task_id: 'task-1', status: 'queued', progress: {} },
    });
  });

  it('treats a maintenance task interrupted by an app restart as terminal', () => {
    expect(referenceLibraryTaskIsActive({
      task_id: 'task-interrupted',
      status: 'interrupted',
    })).toBe(false);
  });

  it('discovers first, shows paths, and starts only selected games after confirmation', async () => {
    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={t} /></MantineProvider>);

    expect(await screen.findAllByText('Victoria 3')).not.toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'settings_reference_auto_build' }));

    await waitFor(() => expect(translationService.discoverReferenceLibraries).toHaveBeenCalled());
    expect(await screen.findByText('settings_reference_discovery_title')).toBeInTheDocument();
    expect(screen.getAllByText(status.libraries[0].root_path).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /settings_reference_start_selected/ }));

    await waitFor(() => expect(translationService.startReferenceLibraryJob).toHaveBeenCalledWith({
      operations: [{
        game_id: 'victoria3',
        localization_path: status.libraries[0].root_path,
        action: 'update',
      }],
    }));
  });

  it('restores an active task after the settings page remounts', async () => {
    translationService.getActiveReferenceLibraryJob.mockResolvedValue({
      data: {
        task_id: 'task-restore',
        status: 'running',
        progress: {
          percent: 42,
          per_game: [{ game_id: 'victoria3', game_name: 'Victoria 3', status: 'scanning', processed_files: 4, total_files: 10 }],
        },
      },
    });
    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={t} /></MantineProvider>);

    expect(await screen.findByText('settings_reference_task_title')).toBeInTheDocument();
    expect(screen.getByText('settings_reference_files_progress:{"current":4,"total":10}')).toBeInTheDocument();
  });

  it('requires explicit confirmation before deleting a game corpus', async () => {
    translationService.deleteReferenceLibrary.mockResolvedValue({ data: { status: 'success' } });
    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={t} /></MantineProvider>);

    await screen.findAllByText('Victoria 3');
    fireEvent.click(screen.getByRole('button', { name: 'settings_reference_delete_for:{"game":"Victoria 3"}' }));
    expect(await screen.findByText('settings_reference_delete_title')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'settings_reference_delete_confirm' }));

    await waitFor(() => expect(translationService.deleteReferenceLibrary).toHaveBeenCalledWith('victoria3'));
  });

  it('shows a per-game error for a partially failed maintenance task', async () => {
    translationService.getActiveReferenceLibraryJob.mockResolvedValue({
      data: {
        task_id: 'task-partial',
        status: 'running',
        progress: {
          percent: 50,
          games: [{
            game_id: 'victoria3',
            game_name: 'Victoria 3',
            status: 'running',
            stage: 'indexing',
          }],
        },
      },
    });
    translationService.getReferenceLibraryJob.mockResolvedValue({
      data: {
        task_id: 'task-partial',
        status: 'partial_failed',
        message: 'Reference library maintenance finished with errors.',
        progress: {
          percent: 100,
          games: [{
            game_id: 'victoria3',
            game_name: 'Victoria 3',
            status: 'failed',
            stage: 'failed',
            error: 'The localization folder is unreadable.',
          }],
        },
      },
    });

    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={t} /></MantineProvider>);

    expect(await screen.findByText('settings_reference_task_title')).toBeInTheDocument();
    expect(await screen.findByText('The localization folder is unreadable.', {}, { timeout: 2500 })).toBeInTheDocument();
  });
});
