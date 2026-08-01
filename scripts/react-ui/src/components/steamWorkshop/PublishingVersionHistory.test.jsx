import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import PublishingVersionHistory from './PublishingVersionHistory';

const adoptVersion = vi.fn();
const setOpenedVersion = vi.fn();

vi.mock('./usePublishingVersionHistory', () => ({
  usePublishingVersionHistory: () => {
    const [openedVersion, setOpenedVersionState] = React.useState(null);
    const versions = [
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
    ];

    return {
      adoptVersion,
      busyVersionId: null,
      error: '',
      filter: 'all',
      filteredVersions: versions,
      isLoading: false,
      isSelected: (version) => version.version_id === 'cover-1',
      openedVersion,
      setFilter: vi.fn(),
      setOpenedVersion: (version) => {
        setOpenedVersion(version);
        setOpenedVersionState(version);
      },
      versions,
    };
  },
}));

describe('PublishingVersionHistory', () => {
  it('shows both asset types and adopts a candidate only from the history view', async () => {
    render(
      <MantineProvider>
        <MemoryRouter initialEntries={['/steam-workshop/workspace-1/history']}>
          <LocationProbe />
          <PublishingVersionHistory workspaceId="workspace-1" />
        </MemoryRouter>
      </MantineProvider>,
    );

    expect(screen.getByText('封面图 第 1 版')).toBeInTheDocument();
    expect(screen.getByText('工坊描述 第 2 版')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '载入编辑' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '载入编辑' }));
    expect(screen.getByTestId('location')).toHaveTextContent(
      '/steam-workshop/workspace-1/cover?coverVersionId=cover-1',
    );
    expect(adoptVersion).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole('button', { name: '打开' })[1]);
    expect(setOpenedVersion).toHaveBeenCalledWith(expect.objectContaining({
      version_id: 'description-2',
    }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.closest('[data-remis-surface="elevated"]')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-header')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-title')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-body')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '设为采用' }));
    expect(adoptVersion).toHaveBeenCalledWith(expect.objectContaining({
      version_id: 'description-2',
    }));
  });
});

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
};
