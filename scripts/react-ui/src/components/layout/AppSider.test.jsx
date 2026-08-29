import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FEATURES } from '../../config/features';
import { AppSider } from './AppSider';

const navigateMock = vi.fn();
const startTourMock = vi.fn();

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
  useLocation: () => ({ pathname: '/settings' }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => ({
      page_title_agent_workshop: 'Format Repair',
    }[key] || key),
  }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    startTour: startTourMock,
  }),
}));

vi.mock('../../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => ({
    activeCount: 0,
    attentionCount: 0,
    openTaskCenter: vi.fn(),
    opened: false,
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

  it('organizes mature workflows into stable user domains without a more bucket', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    expect(screen.getByText('nav_projects')).toBeInTheDocument();
    expect(screen.getByText('nav_translation_workflow')).toBeInTheDocument();
    expect(screen.getByText('nav_quality_terminology')).toBeInTheDocument();
    expect(screen.getByText('nav_mod_monitor')).toBeInTheDocument();
    expect(screen.getByText('Format Repair')).toBeInTheDocument();
    expect(screen.queryByText('nav_more')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('neologism_review.title'));
    expect(navigateMock).toHaveBeenCalledWith('/neologism-review');
  });

  it('keeps domain menus available from the collapsed icon rail', async () => {
    renderWithProvider(<AppSider />);

    fireEvent.click(screen.getByTitle('nav_projects'));

    expect(await screen.findByText('nav_mod_monitor')).toBeInTheDocument();
  });

  it('matches Copilot navigation visibility to the active build profile', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    const copilotEntry = screen.queryByText('page_title_copilot');
    if (FEATURES.ENABLE_REMIS_COPILOT) {
      expect(copilotEntry).toBeInTheDocument();
    } else {
      expect(copilotEntry).not.toBeInTheDocument();
    }
  });

  it('shows a dedicated Copilot entry in the Agent Preview profile', () => {
    renderWithProvider(<AppSider features={{ ENABLE_REMIS_COPILOT: true }} />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);
    fireEvent.click(screen.getByText('page_title_copilot'));

    expect(navigateMock).toHaveBeenCalledWith('/copilot');
  });

  it('localizes the sidebar pin toggle tooltip', () => {
    renderWithProvider(<AppSider />);

    const sidebar = document.getElementById('sidebar-nav');
    fireEvent.mouseEnter(sidebar);

    expect(screen.getByTitle('sidebar.pin')).toBeInTheDocument();
  });
});
