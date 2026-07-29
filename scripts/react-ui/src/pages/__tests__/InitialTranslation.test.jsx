import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';

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

vi.mock('../../context/NotificationContextCore', () => ({
  useNotification: () => ({
    notificationStyle: 'minimal',
  }),
}));

vi.mock('../../context/TaskCenterContextCore', () => ({
  useTaskCenter: () => ({ openTaskCenter: vi.fn() }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    setPageContext: setPageContextMock,
    startTour: startTourMock,
  }),
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

vi.mock('../../context/TranslationContextCore', () => ({
  useTranslationContext: () => {
    const [activeStep, setActiveStep] = React.useState(0);
    const [selectedProjectId, setSelectedProjectId] = React.useState(null);

    return {
      activeStep,
      setActiveStep,
      setTaskId: vi.fn(),
      taskId: null,
      taskStatus: null,
      isProcessing: false,
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
    renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('Extra Terms')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Russian'));

    await waitFor(() => {
      const checkpointCalls = apiPostMock.mock.calls.filter(([url]) => url === '/api/translation/checkpoint-status');
      expect(checkpointCalls.at(-1)).toEqual([
        '/api/translation/checkpoint-status',
        {
          mod_name: 'Test Project',
          target_lang_codes: ['ru'],
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

  it('keeps the project source language out of target language choices', async () => {
    renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('Chinese')).toBeInTheDocument();
      expect(screen.getByText('Russian')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('English')).toBeInTheDocument();
    expect(screen.queryByText('English')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Chinese' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Russian' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', {
      name: 'initial_translation_start_choose_target',
    })).toBeDisabled();
  });

  it('renders checkpoint status alert and resume details card when checkpoints exist', async () => {
    const mockCheckpointResponse = {
      exists: true,
      completed_count: 5,
      total_files_estimate: 10,
      metadata: {
        current_batch: 2,
        total_batches: 5,
        last_saved_at: '2026-05-28 07:00:00',
        last_completed_file: 'events/test.yml',
      },
      targets: [
        {
          target_lang_code: 'zh-CN',
          completed_count: 5,
          last_saved_at: '2026-05-28 07:00:00',
          metadata: {
            current_batch: 2,
            total_batches: 5,
            last_completed_file: 'events/test.yml',
          }
        }
      ]
    };

    apiPostMock.mockImplementation((url) => {
      if (url === '/api/translation/checkpoint-status') {
        return Promise.resolve({ data: mockCheckpointResponse });
      }
      return Promise.resolve({ data: { exists: false } });
    });

    try {
      renderPage(['/?projectId=proj-1']);

      await waitFor(() => {
        expect(screen.getByText('Chinese')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('Chinese'));

      await waitFor(() => {
        expect(screen.getByText('检测到可用断点')).toBeInTheDocument();
      });

      expect(screen.getByText('断点续传详情')).toBeInTheDocument();
      expect(screen.queryByText('zh-CN')).not.toBeInTheDocument();

      // 在 waitFor 之后，重新拉取并点击“展开”按钮以保证渲染稳定性
      await waitFor(() => {
        const expandButtons = screen.getAllByRole('button', { name: '展开' });
        expect(expandButtons.length).toBeGreaterThan(0);
      });

      const expandButtons = screen.getAllByRole('button', { name: '展开' });
      fireEvent.click(expandButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('zh-CN')).toBeInTheDocument();
        expect(screen.getByText('已完成文件：{{count}}')).toBeInTheDocument();
      });
    } finally {
      apiPostMock.mockImplementation((url) => {
        if (url === '/api/translation/checkpoint-status') {
          return Promise.resolve({ data: { exists: false } });
        }
        return Promise.reject(new Error(`Unhandled POST ${url}`));
      });
    }
  });

  it('manages embedded workshop toggle and custom provider/model linkage', async () => {
    const { container } = renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('格式修复台设置')).toBeInTheDocument();
    });

    // 重新获取展开按钮以保证渲染稳定性
    await waitFor(() => {
      const expandButtons = screen.getAllByRole('button', { name: '展开' });
      expect(expandButtons.length).toBeGreaterThan(1);
    });

    const expandButtons = screen.getAllByRole('button', { name: '展开' });
    fireEvent.click(expandButtons[1]);

    await waitFor(() => {
      expect(screen.getByText('当前将跟随主翻译配置：{{provider}} / {{model}}')).toBeInTheDocument();
    });

    // 通过 ID 稳定选择 Switch 的 input 并点击
    const workshopSwitch = container.querySelector('#embedded-workshop-switch');
    expect(workshopSwitch).toBeInTheDocument();
    expect(workshopSwitch.checked).toBe(true);

    fireEvent.click(workshopSwitch);
    expect(workshopSwitch.checked).toBe(false);

    // 状态切换后展开按钮变为了收起按钮并被禁用
    const collapseButton = screen.getByRole('button', { name: '收起' });
    expect(collapseButton).toBeDisabled();
  });

  it('seeds embedded workshop independent settings from the primary provider and model', async () => {
    const { container } = renderPage(['/?projectId=proj-1']);

    await waitFor(() => {
      expect(screen.getByText('格式修复台设置')).toBeInTheDocument();
    });

    const expandButtons = screen.getAllByRole('button', { name: '展开' });
    fireEvent.click(expandButtons[1]);

    await waitFor(() => {
      expect(screen.getByText('当前将跟随主翻译配置：{{provider}} / {{model}}')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('默认跟随当前翻译 API 与模型'));

    await waitFor(() => {
      expect(screen.getByText('当前使用独立校对配置：{{provider}} / {{model}}')).toBeInTheDocument();
    });

    const workshopProviderSelect = findSingleSelectByOptions(container, ['gemini', 'openai']);
    expect(workshopProviderSelect).toBeTruthy();
    expect(workshopProviderSelect.value).toBe('gemini');
    expect(screen.getAllByDisplayValue('gemini-flash').length).toBeGreaterThan(0);
  });
});
