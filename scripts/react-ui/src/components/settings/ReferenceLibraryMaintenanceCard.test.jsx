import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { open } from '@tauri-apps/plugin-dialog';
import api from '../../utils/api';
import ReferenceLibraryMaintenanceCard from './ReferenceLibraryMaintenanceCard';

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));
vi.mock('../../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

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

describe('ReferenceLibraryMaintenanceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: status });
    api.post.mockResolvedValue({ data: { built: [status.libraries[0]] } });
  });

  it('shows the persisted library and explicitly starts auto build', async () => {
    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={(key) => key} /></MantineProvider>);

    expect(await screen.findAllByText('Victoria 3')).not.toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'settings_reference_auto_build' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/api/system/reference-library/auto-build',
    ));
  });

  it('builds a manually selected profile-specific folder', async () => {
    open.mockResolvedValue('I:/SteamLibrary/steamapps/common/Victoria 3/game/localization');
    render(<MantineProvider><ReferenceLibraryMaintenanceCard t={(key) => key} /></MantineProvider>);

    await screen.findAllByText('Victoria 3');
    fireEvent.click(screen.getByRole('button', { name: 'settings_reference_manual_build' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/api/system/reference-library/build',
      {
        game_id: 'victoria3',
        localization_path: 'I:/SteamLibrary/steamapps/common/Victoria 3/game/localization',
      },
    ));
  });
});
