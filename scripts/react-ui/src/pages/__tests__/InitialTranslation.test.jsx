import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';

import InitialTranslation from '../InitialTranslation';

const setPageContextMock = vi.fn();
const startTourMock = vi.fn();
const { apiDeleteMock, apiGetMock, apiPostMock } = vi.hoisted(() => {
  const get = vi.fn((url) => {
    if (url === '/api/config') {
      return Promise.resolve({
        data: {
          game_profiles: {
            vic3: { id: 'victoria3', name: 'Victoria 3' },
          },
          languages: {
            en: { code: 'en', key: 'l_english', name: 'English' },
            zh: { code: 'zh-CN', key: 'l_simp_chinese', name: 'Chinese' },
            ru: { code: 'ru', key: 'l_russian', name: 'Russian' },
          },
          api_providers: [
            {
              value: 'gemini',
              label: 'Gemini',
              available_models: ['gemini-pro', 'gemini-flash'],
              selected_model: 'gemini-flash',
            },
            {
              value: 'openai',
              label: 'OpenAI',
              available_models: ['gpt-4.1-mini', 'gpt-4.1'],
              selected_model: 'gpt-4.1-mini',
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

    if (url === '/api/glossaries/vic3') {
      return Promise.resolve({
        data: [
          {
            glossary_id: 1,
            name: 'Main Glossary',
            game_id: 'vic3',
            is_main: true,
          },
          {
            glossary_id: 2,
            name: 'Extra Terms',
            game_id: 'vic3',
            is_main: false,
          },
        ],
      });
    }

    return Promise.reject(new Error(`Unhandled GET ${url}`));
  });

  const post = vi.fn((url) => {
    if (url === '/api/translation/checkpoint-status') {
      return Promise.resolve({
        data: {
          exists: false,
        },
      });
    }

    return Promise.reject(new Error(`Unhandled POST ${url}`));
  });

  return {
    apiGetMock: get,
    apiPostMock: post,
    apiDeleteMock: vi.fn(),
  };
});

vi.mock('../../utils/api', () => ({
  default: {
    get: apiGetMock,
    post: apiPostMock,
    delete: apiDeleteMock,
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => {
      if (typeof options === 'string') {
        return options;
      }

      if (options && typeof options === 'object' && 'defaultValue' in options) {
        return options.defaultValue;
      }

      return key;
    },
  }),
}));

vi.mock('../../context/NotificationContext', () => ({
  useNotification: () => ({
    notificationStyle: 'minimal',
  }),
}));

vi.mock('../../context/TutorialContext', () => ({
  useTutorial: () => ({
    setPageContext: setPageContextMock,
    startTour: startTourMock,
  }),
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

vi.mock('../../context/TranslationContext', () => ({
  useTranslationContext: () => {
    const [activeStep, setActiveStep] = React.useState(0);
    const [selectedProjectId, setSelectedProjectId] = React.useState(null);

    return {
      activeStep,
      setActiveStep,
      setTaskId: vi.fn(),
      taskStatus: null,
      setIsProcessing: vi.fn(),
      translationDetails: null,
      setTranslationDetails: vi.fn(),
      selectedProjectId,
      setSelectedProjectId,
      resetTranslation: vi.fn(),
    };
  },
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

const renderPage = (initialEntries = ['/']) =>
  render(
    <MantineProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <InitialTranslation />
      </MemoryRouter>
    </MantineProvider>,
  );

const findSingleSelectByOptions = (container, optionValues) => Array.from(container.querySelectorAll('select:not([multiple])'))
  .find((select) => optionValues.every((value) => Array.from(select.options).some((option) => option.value === value)));

const findMultiSelectByOptions = (container, optionValues) => Array.from(container.querySelectorAll('select[multiple]'))
  .find((select) => optionValues.every((value) => Array.from(select.options).some((option) => option.value === value)));

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

    expect(setPageContextMock).toHaveBeenCalledWith(expect.any(Function));
  });

  it('loads non-main glossaries for the selected project game', async () => {
    renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('Extra Terms')).toBeInTheDocument();
    });

    const api = (await import('../../utils/api')).default;
    expect(api.get).toHaveBeenCalledWith('/api/glossaries/vic3');
    expect(screen.queryByText('Main Glossary')).not.toBeInTheDocument();
  });

  it('refreshes checkpoint hint request when target languages change', async () => {
    const { container } = renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('Extra Terms')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith('/api/translation/checkpoint-status', {
        mod_name: 'Test Project',
        target_lang_codes: ['zh-CN'],
      });
    });

    fireEvent.click(screen.getByText('Russian'));

    await waitFor(() => {
      const checkpointCalls = apiPostMock.mock.calls.filter(([url]) => url === '/api/translation/checkpoint-status');
      expect(checkpointCalls.at(-1)).toEqual([
        '/api/translation/checkpoint-status',
        {
          mod_name: 'Test Project',
          target_lang_codes: ['zh-CN', 'ru'],
        },
      ]);
    });
  });

  it('switches to the selected provider model set when the primary provider changes', async () => {
    const { container } = renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('Extra Terms')).toBeInTheDocument();
    });

    const providerSelect = findSingleSelectByOptions(container, ['gemini', 'openai']);
    expect(providerSelect).toBeTruthy();
    fireEvent.change(providerSelect, { target: { value: 'openai' } });

    await waitFor(() => {
      expect(screen.getByDisplayValue('gpt-4.1-mini')).toBeInTheDocument();
    });
  });
});
