import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ThemeContext from '../ThemeContext';
import api from '../utils/api';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import SettingsPage from './SettingsPage';

const setPageContextMock = vi.fn();

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('../context/TutorialContextCore', () => ({
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
  useTutorial: () => ({
    setPageContext: setPageContextMock,
    startTour: vi.fn(),
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => options?.defaultValue || key,
    i18n: {
      language: 'en',
      changeLanguage: vi.fn(),
    },
  }),
}));

vi.mock('../components/ApiSettingsTab', () => ({ default: () => <div /> }));
vi.mock('../components/PromptSettingsTab', () => ({ default: () => <div /> }));
vi.mock('../components/VersionInfoTab', () => ({ default: () => <div /> }));
vi.mock('../components/settings/CopilotSettingsTab', () => ({
  default: function MockCopilotSettingsTab() {
    const [dirty, setDirty] = React.useState(false);
    useUnsavedChangesGuard({
      id: 'test-copilot-settings',
      isDirty: dirty,
      onDiscard: () => setDirty(false),
    });
    return (
      <div>
        <div>shared-copilot-settings</div>
        <button type="button" onClick={() => setDirty(true)}>make-copilot-dirty</button>
      </div>
    );
  },
}));
vi.mock('../config/features', () => ({ FEATURES: { ENABLE_REMIS_COPILOT: true } }));

const renderSettings = () => {
  const router = createMemoryRouter([
    { path: '/settings', element: <SettingsPage /> },
    { path: '/home', element: <div>home-page</div> },
  ], { initialEntries: ['/settings'] });

  render(
    <MantineProvider>
      <ThemeContext.Provider value={{ theme: 'scifi', toggleTheme: vi.fn() }}>
        <RouterProvider router={router} />
      </ThemeContext.Provider>
    </MantineProvider>,
  );
  return router;
};

describe('SettingsPage database recovery controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('remis_tutorial_settings_prompt_seen_v1', 'true');
    api.get.mockResolvedValue({ data: { rpm_limit: 40 } });
    api.post.mockResolvedValue({
      data: { status: 'success', database_file: 'remis.sqlite' },
    });
  });

  it('opens the database folder without starting a reset', async () => {
    renderSettings();

    expect(await screen.findByText('settings_database_file_label')).toBeInTheDocument();
    expect(screen.getByText('remis.sqlite')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'button_open_folder' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/system/open-database-folder');
    });
    expect(api.post).not.toHaveBeenCalledWith('/api/system/reset-db');
  });

  it('describes task history as part of the reset impact', async () => {
    renderSettings();

    fireEvent.click(await screen.findByRole('button', { name: 'btn_reset_db' }));

    expect(await screen.findByText('modal_reset_db_impact_2')).toBeInTheDocument();
    expect(screen.getByText('modal_reset_db_safe_3')).toBeInTheDocument();
  });

  it('exposes a dedicated Copilot settings tab in Agent Preview', async () => {
    renderSettings();

    fireEvent.click(await screen.findByRole('tab', { name: '小助手设置' }));
    expect(screen.getByText('shared-copilot-settings')).toBeInTheDocument();
  });

  it('protects tab changes and route navigation until the user chooses', async () => {
    renderSettings();

    fireEvent.click(await screen.findByRole('tab', { name: '小助手设置' }));
    fireEvent.click(screen.getByRole('button', { name: 'make-copilot-dirty' }));
    fireEvent.click(screen.getByRole('tab', { name: 'settings_general' }));

    expect((await screen.findAllByText('您还有未保存的改动，确定要现在离开吗？')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '放弃改动并离开' }));
    await waitFor(() => expect(screen.getByRole('tab', { name: 'settings_general' })).toHaveAttribute('aria-selected', 'true'));
  });
});
