import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, useLocation } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import AgentWorkshopPage from './AgentWorkshopPage';

vi.mock('../hooks/useAgentWorkshopController', () => ({
  useAgentWorkshopController: () => ({
    active: 2,
    apiProviders: [],
    approvalOpen: false,
    archiveInfo: { source_entry_count: 10 },
    batchSizeLimit: '10',
    concurrencyLimit: '1',
    currentRunTaskId: 'format-scan-zero',
    currentIssue: null,
    executing: false,
    executionLogs: [],
    executionStats: null,
    filteredProjects: [],
    fixedIssues: [],
    gameFilter: 'all',
    gameFilterOptions: [],
    groupedIssues: [],
    handleProviderChange: vi.fn(),
    isCached: false,
    issueTypeSummary: [],
    issues: [],
    localizeIssueDetails: () => '',
    localizeIssueLabel: (value) => value,
    modelOptions: [],
    progress: 0,
    rpmLimit: '40',
    scanLoading: false,
    searchQuery: '',
    selectedModel: '',
    selectedProjectId: 'project-1',
    selectedProvider: '',
    setActive: vi.fn(),
    setBatchSizeLimit: vi.fn(),
    setConcurrencyLimit: vi.fn(),
    setGameFilter: vi.fn(),
    setRpmLimit: vi.fn(),
    setSearchQuery: vi.fn(),
    setSelectedModel: vi.fn(),
    showTutorialPrompt: false,
    t: (key, options) => options?.defaultValue || key,
  }),
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

describe('Agent Workshop deterministic scan feedback', () => {
  it('shows the exact completed scan task even when no issue was found', () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <AgentWorkshopPage />
          <LocationProbe />
        </MemoryRouter>
      </MantineProvider>,
    );

    expect(screen.getByText(/format-scan-zero/)).toBeInTheDocument();
    expect(screen.getByText('This format scan is recorded in Task Center.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'task_center.view_task' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/tasks/format-scan-zero');
  });
});
