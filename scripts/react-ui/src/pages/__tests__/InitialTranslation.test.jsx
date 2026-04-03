import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';

import InitialTranslation from '../InitialTranslation';

vi.mock('../../utils/api', () => ({
  default: {
    get: vi.fn((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          data: {
            game_profiles: {
              vic3: { id: 'victoria3', name: 'Victoria 3' },
            },
            languages: {
              en: { code: 'en', key: 'l_english', name: 'English' },
              zh: { code: 'zh-CN', key: 'l_simp_chinese', name: 'Chinese' },
            },
            api_providers: [
              {
                value: 'gemini',
                label: 'Gemini',
                available_models: ['gemini-pro'],
                selected_model: 'gemini-pro',
              },
            ],
          },
        });
      }

      if (url === '/api/projects') {
        return Promise.resolve({
          data: [
            {
              project_id: 'proj-1',
              name: 'Test Project',
              game_id: 'vic3',
              status: 'active',
              source_language: 'en',
            },
          ],
        });
      }

      if (url === '/api/prompts') {
        return Promise.resolve({
          data: {
            custom_global_prompt: '',
          },
        });
      }

      return Promise.reject(new Error(`Unhandled GET ${url}`));
    }),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, fallback) => fallback || key,
  }),
}));

vi.mock('../../context/NotificationContext', () => ({
  useNotification: () => ({
    notificationStyle: 'minimal',
  }),
}));

vi.mock('../../context/TutorialContext', () => ({
  useTutorial: () => ({
    setPageContext: vi.fn(),
  }),
}));

vi.mock('../../context/TranslationContext', () => ({
  useTranslationContext: () => ({
    activeStep: 0,
    setActiveStep: vi.fn(),
    setTaskId: vi.fn(),
    taskStatus: null,
    setIsProcessing: vi.fn(),
    translationDetails: null,
    setTranslationDetails: vi.fn(),
    selectedProjectId: null,
    setSelectedProjectId: vi.fn(),
    resetTranslation: vi.fn(),
  }),
}));

vi.mock('../../components/TaskRunner', () => ({
  default: () => <div>TaskRunner</div>,
}));

class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = ResizeObserver;

const renderPage = () =>
  render(
    <MantineProvider>
      <MemoryRouter>
        <InitialTranslation />
      </MemoryRouter>
    </MantineProvider>,
  );

describe('InitialTranslation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders project selection without crashing', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getAllByText('translation_page.subtitle').length).toBeGreaterThan(0);
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
  });
});
