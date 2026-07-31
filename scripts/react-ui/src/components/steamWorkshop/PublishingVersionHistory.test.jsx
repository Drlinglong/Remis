import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PublishingVersionHistory from './PublishingVersionHistory';

const adoptVersion = vi.fn();
const setOpenedVersion = vi.fn();

vi.mock('./usePublishingVersionHistory', () => ({
  usePublishingVersionHistory: () => ({
    adoptVersion,
    busyVersionId: null,
    error: '',
    filter: 'all',
    filteredVersions: [
      {
        version_id: 'cover-1',
        asset_type: 'cover',
        sequence: 1,
        source: 'manual',
        created_at: '2026-07-31T10:00:00Z',
      },
      {
        version_id: 'description-2',
        asset_type: 'description',
        sequence: 2,
        source: 'model',
        language: 'zh',
        bbcode: '[b]描述[/b]',
        created_at: '2026-07-31T11:00:00Z',
      },
    ],
    isLoading: false,
    isSelected: (version) => version.version_id === 'cover-1',
    openedVersion: null,
    setFilter: vi.fn(),
    setOpenedVersion,
    versions: [
      { version_id: 'cover-1', asset_type: 'cover' },
      { version_id: 'description-2', asset_type: 'description' },
    ],
  }),
}));

describe('PublishingVersionHistory', () => {
  it('shows both asset types and adopts a candidate only from the history view', () => {
    render(
      <MantineProvider>
        <PublishingVersionHistory workspaceId="workspace-1" />
      </MantineProvider>,
    );

    expect(screen.getByText('封面图 #1')).toBeInTheDocument();
    expect(screen.getByText('工坊描述 #2')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '打开' })[1]);
    expect(setOpenedVersion).toHaveBeenCalledWith(expect.objectContaining({
      version_id: 'description-2',
    }));
    fireEvent.click(screen.getByRole('button', { name: '设为采用' }));
    expect(adoptVersion).toHaveBeenCalledWith(expect.objectContaining({
      version_id: 'description-2',
    }));
  });
});
