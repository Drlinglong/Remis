import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import PublishingVersionHistory from './PublishingVersionHistory';

const deleteVersion = vi.fn().mockResolvedValue(true);

vi.mock('./usePublishingVersionHistory', () => ({
  usePublishingVersionHistory: () => ({
    adoptVersion: vi.fn(),
    busyVersionId: null,
    deleteVersion,
    error: '',
    filter: 'all',
    filteredVersions: [
      { version_id: 'selected', asset_type: 'description', sequence: 1, created_at: '2026-08-01', source: 'manual' },
      { version_id: 'candidate', asset_type: 'description', sequence: 2, created_at: '2026-08-01', source: 'manual' },
    ],
    isLoading: false,
    isSelected: (version) => version.version_id === 'selected',
    openedVersion: null,
    setFilter: vi.fn(),
    setOpenedVersion: vi.fn(),
    versions: [
      { version_id: 'selected', asset_type: 'description' },
      { version_id: 'candidate', asset_type: 'description' },
    ],
  }),
}));

// Regression: ISSUE-005 — individual publishing versions could not be deleted
// Found by /qa on 2026-08-01
// Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-08-01.md
describe('PublishingVersionHistory deletion', () => {
  it('protects the selected version and confirms deletion of a candidate', async () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <PublishingVersionHistory workspaceId="workspace-1" />
        </MemoryRouter>
      </MantineProvider>,
    );

    expect(screen.getByRole('button', { name: '采用中，不可删除' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '删除' }));
    expect(await screen.findByText(/确定删除工坊描述 #2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => expect(deleteVersion).toHaveBeenCalledWith(expect.objectContaining({
      version_id: 'candidate',
    })));
  });
});
