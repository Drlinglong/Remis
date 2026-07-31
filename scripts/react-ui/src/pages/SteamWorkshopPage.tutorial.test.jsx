import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SteamWorkshopPage from './SteamWorkshopPage';

const setPageContext = vi.fn();
const startTour = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('../context/TutorialContextCore', () => ({
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
  useTutorial: () => ({ setPageContext, startTour }),
}));

vi.mock('../components/steamWorkshop/SteamWorkshopOverview', () => ({
  default: () => <button type="button">新建工作区</button>,
}));

vi.mock('../components/steamWorkshop/SteamWorkshopWorkspace', () => ({
  default: () => <div role="tablist">工作区内容</div>,
}));

const renderPage = (entry) => render(
  <MantineProvider>
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/steam-workshop" element={<SteamWorkshopPage />} />
        <Route path="/steam-workshop/:workspaceId/:section" element={<SteamWorkshopPage />} />
      </Routes>
    </MemoryRouter>
  </MantineProvider>,
);

describe('SteamWorkshopPage tutorial entry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('offers the first-visit overview tour and starts the workspace tutorial', () => {
    renderPage('/steam-workshop');

    expect(setPageContext).toHaveBeenCalledWith('steam-workshop');
    expect(screen.getByText('tutorial.steam_workshop.prompt.message'))
      .toBeInTheDocument();
    expect(document.querySelector('#steam-workshop-page')).toBeInTheDocument();
    expect(document.querySelector('#steam-workshop-content')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'tutorial.auto_start_prompt.confirm' }));

    expect(startTour).toHaveBeenCalledWith('steam-workshop');
    expect(localStorage.getItem('remis_tutorial_steam-workshop_prompt_seen_v1')).toBe('true');
  });

  it('sets a section-specific context without repeatedly prompting inside a workspace', () => {
    renderPage('/steam-workshop/workspace-1/history');

    expect(setPageContext).toHaveBeenCalledWith('steam-workshop-history');
    expect(screen.queryByText('tutorial.steam_workshop.prompt.message'))
      .not.toBeInTheDocument();
  });
});
