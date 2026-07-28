import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import IncrementalTranslationPage from './IncrementalTranslationPage';
import useIncrementalTranslation from '../hooks/useIncrementalTranslation';

const { setPageContextMock } = vi.hoisted(() => ({
  setPageContextMock: vi.fn(),
}));

vi.mock('../context/CopilotContext', () => ({
  useRemisCopilotContext: () => ({ registerPageContext: vi.fn() }),
}));

vi.mock('../hooks/useIncrementalTranslation', () => ({
  default: vi.fn(),
}));

vi.mock('../context/NotificationContextCore', () => ({
  useNotification: () => ({ notificationStyle: {} }),
}));

vi.mock('../context/NotificationContext', () => ({
  useNotification: () => ({ notificationStyle: {} }),
}));

vi.mock('../context/TutorialContextCore', () => ({
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
  useTutorial: () => ({
    setPageContext: setPageContextMock,
    startTour: vi.fn(),
  }),
}));

vi.mock('../context/TutorialContext', () => ({
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
  useTutorial: () => ({
    setPageContext: setPageContextMock,
    startTour: vi.fn(),
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => options?.defaultValue || key,
  }),
}));

const renderPage = () =>
  render(
    <MantineProvider>
      <MemoryRouter>
        <IncrementalTranslationPage />
      </MemoryRouter>
    </MantineProvider>
  );

describe('IncrementalTranslationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useIncrementalTranslation.mockReturnValue({
      active: 0,
      setActive: vi.fn(),
      handleSelectProject: vi.fn(),
      resetPersistedState: vi.fn(),
      showTutorialPrompt: false,
      setShowTutorialPrompt: vi.fn(),
    });
  });

  it('renders safely while array state is still unavailable', () => {
    renderPage();

    expect(screen.getByText('incremental_translation.title')).toBeInTheDocument();
    expect(screen.getByText('common.nothing_found')).toBeInTheDocument();
  });
});
