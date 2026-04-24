import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppSider } from './AppSider';

const navigateMock = vi.fn();
const startTourMock = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
  useLocation: () => ({ pathname: '/settings' }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

vi.mock('../../context/TutorialContext', () => ({
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
});
