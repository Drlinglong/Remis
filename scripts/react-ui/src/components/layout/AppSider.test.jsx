import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppSider } from './AppSider';

const navigateMock = vi.fn();
const startTourMock = vi.fn();

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
  useLocation: () => ({ pathname: '/settings' }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    startTour: startTourMock,
  }),
}));

vi.mock('../../ThemeContext', async () => {
  const ReactModule = await vi.importActual('react');
  return {
    default: ReactModule.createContext({ theme: 'scifi' }),
  };
});

const renderWithProvider = (ui) =>
  render(<MantineProvider>{ui}</MantineProvider>);

describe('AppSider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('expands on hover and navigates when a nav item is clicked', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    fireEvent.click(screen.getByText('page_title_settings'));

    expect(navigateMock).toHaveBeenCalledWith('/settings');
  });

  it('starts the tutorial when the tutorial entry is clicked', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    fireEvent.click(screen.getByText('tutorial.sidebar_tutorial_btn'));

    expect(startTourMock).toHaveBeenCalledOnce();
  });

  it('shows project tracking and the neologism review entry in the main navigation', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    expect(screen.getByText('page_title_project_tracking')).toBeInTheDocument();
    fireEvent.click(screen.getByText('neologism_review.title'));
    expect(navigateMock).toHaveBeenCalledWith('/neologism-review');
  });

  it('keeps the in-development Remis Copilot entry hidden', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    expect(screen.queryByText('page_title_copilot')).not.toBeInTheDocument();
  });

  it('localizes the sidebar pin toggle tooltip', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    expect(screen.getByTitle('sidebar.pin')).toBeInTheDocument();
  });
});
