import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ThemeContext from '../ThemeContext';
import api from '../utils/api';
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
    t: (key) => key,
    i18n: {
      language: 'en',
      changeLanguage: vi.fn(),
    },
  }),
}));

vi.mock('../components/ApiSettingsTab', () => ({ default: () => <div /> }));
vi.mock('../components/PromptSettingsTab', () => ({ default: () => <div /> }));
vi.mock('../components/VersionInfoTab', () => ({ default: () => <div /> }));

describe('SettingsPage database recovery controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('remis_tutorial_settings_prompt_seen_v1', 'true');
    api.get.mockResolvedValue({ data: { rpm_limit: 40 } });
    api.post.mockResolvedValue({ data: { status: 'success' } });
  });

  it('opens the database folder without starting a reset', async () => {
    render(
      <MantineProvider>
        <ThemeContext.Provider value={{ theme: 'scifi', toggleTheme: vi.fn() }}>
          <SettingsPage />
        </ThemeContext.Provider>
      </MantineProvider>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'button_open_folder' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/system/open-database-folder');
    });
    expect(api.post).not.toHaveBeenCalledWith('/api/system/reset-db');
  });

  it('describes task history as part of the reset impact', async () => {
    render(
      <MantineProvider>
        <ThemeContext.Provider value={{ theme: 'scifi', toggleTheme: vi.fn() }}>
          <SettingsPage />
        </ThemeContext.Provider>
      </MantineProvider>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'btn_reset_db' }));

    expect(await screen.findByText('modal_reset_db_impact_2')).toBeInTheDocument();
    expect(screen.getByText('modal_reset_db_safe_3')).toBeInTheDocument();
  });
});
