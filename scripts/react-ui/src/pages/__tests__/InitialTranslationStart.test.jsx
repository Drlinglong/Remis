import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';

import InitialTranslation from '../InitialTranslation';

const { apiDeleteMock, apiGetMock, apiPostMock } = vi.hoisted(() => ({
  apiDeleteMock: vi.fn(),
  apiGetMock: vi.fn(),
  apiPostMock: vi.fn(),
}));

vi.mock('../../utils/api', () => ({
  default: {
    delete: apiDeleteMock,
    get: apiGetMock,
    post: apiPostMock,
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => {
      const copy = {
        button_back: '返回',
        button_start_translation: '开始翻译',
        initial_translation_clear_all: '清除',
        initial_translation_continue: '继续上次翻译',
        initial_translation_ready_title: '准备翻译',
        initial_translation_select_all: '全选',
        initial_translation_start_checking: '正在检查配置…',
        initial_translation_start_choose_model: '请选择 AI 模型',
        initial_translation_start_choose_target: '请选择目标语言',
        initial_translation_start_missing_api_key: '请先配置 API 密钥',
        initial_translation_summary_main_glossary_on: '主词典已启用',
        initial_translation_summary_workshop_on: '智能校对已启用',
        initial_translation_target_none: '尚未选择目标语言',
        initial_translation_target_required: '请选择至少一种目标语言。',
        initial_translation_target_section_title: '翻译为',
      };
      if (key === 'initial_translation_target_selected_count') {
        return `已选择 ${options.count} 种语言`;
      }
      if (key === 'initial_translation_summary_target_count') {
        return `${options.count} 种目标语言`;
      }
      if (typeof options === 'string') {
        return options;
      }
      if (options && typeof options === 'object' && 'defaultValue' in options) {
        return options.defaultValue;
      }
      return copy[key] || key;
    },
  }),
}));

vi.mock('../../context/NotificationContextCore', () => ({
  useNotification: () => ({ notificationStyle: 'minimal' }),
}));

vi.mock('../../context/TutorialContextCore', () => ({
  useTutorial: () => ({
    setPageContext: vi.fn(),
    startTour: vi.fn(),
  }),
  getTutorialKey: (page = 'general') => `remis_tutorial_${page}_v1`,
}));

vi.mock('../../context/TranslationContextCore', () => ({
  useTranslationContext: () => {
    const [activeStep, setActiveStep] = React.useState(0);
    const [selectedProjectId, setSelectedProjectId] = React.useState(null);

    return {
      activeStep,
      isProcessing: false,
      resetTranslation: vi.fn(),
      selectedProjectId,
      setActiveStep,
      setIsProcessing: vi.fn(),
      setSelectedProjectId,
      setTaskId: vi.fn(),
      setTranslationDetails: vi.fn(),
      taskStatus: null,
      translationDetails: null,
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

const configPayload = {
  game_profiles: {
    vic3: { id: 'victoria3', name: 'Victoria 3' },
  },
  languages: {
    zh: { code: 'zh-CN', key: 'l_simp_chinese', name: '简体中文' },
    en: { code: 'en', key: 'l_english', name: 'English' },
    fr: { code: 'fr', key: 'l_french', name: 'Français' },
  },
  api_providers: [
    {
      value: 'gemini',
      label: 'Google Gemini',
      available_models: ['gemini-3-flash-preview'],
      selected_model: 'gemini-3-flash-preview',
    },
    {
      value: 'lm_studio',
      label: 'LM Studio',
      available_models: ['local-model'],
      selected_model: 'local-model',
    },
    {
      value: 'anthropic',
      label: 'Anthropic Claude',
      available_models: ['claude-sonnet'],
      selected_model: 'claude-sonnet',
    },
  ],
};

const renderPage = () => render(
  <MantineProvider>
    <MemoryRouter initialEntries={['/?projectId=project-cn']}>
      <InitialTranslation />
    </MemoryRouter>
  </MantineProvider>,
);

describe('InitialTranslation start contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    apiGetMock.mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({ data: configPayload });
      }
      if (url === '/api/projects') {
        return Promise.resolve({
          data: [{
            project_id: 'project-cn',
            name: 'Chinese Source Project',
            game_id: 'vic3',
            status: 'active',
            source_language: 'zh-CN',
          }],
        });
      }
      if (url === '/api/prompts') {
        return Promise.resolve({ data: { custom_global_prompt: '' } });
      }
      if (url === '/api/api-keys') {
        return Promise.resolve({
          data: [
            { id: 'gemini', is_keyless: false, has_key: true },
            { id: 'lm_studio', is_keyless: true, has_key: false },
            { id: 'anthropic', is_keyless: false, has_key: false },
          ],
        });
      }
      if (url === '/api/glossaries/vic3') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error(`Unhandled GET ${url}`));
    });

    apiPostMock.mockImplementation((url) => {
      if (url === '/api/translation/checkpoint-status') {
        return Promise.resolve({ data: { exists: false } });
      }
      if (url === '/api/translate/start') {
        return Promise.resolve({ data: { task_id: 'task-1' } });
      }
      return Promise.reject(new Error(`Unhandled POST ${url}`));
    });
  });

  it('starts a Chinese-source project only after the user chooses a target language', async () => {
    renderPage();

    const blockedStartButton = await screen.findByRole('button', {
      name: '请选择目标语言',
    });
    expect(blockedStartButton).toBeDisabled();
    expect(screen.getByText('尚未选择目标语言')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '简体中文' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(await screen.findByText('已选择 1 种语言')).toBeInTheDocument();

    const providerSelect = screen.getByLabelText('form_label_api_provider');
    fireEvent.change(providerSelect, {
      target: { value: 'anthropic' },
    });
    expect(await screen.findByRole('button', {
      name: '请先配置 API 密钥',
    })).toBeDisabled();

    fireEvent.change(providerSelect, {
      target: { value: 'lm_studio' },
    });
    await waitFor(() => {
      expect(screen.getByDisplayValue('local-model')).toBeInTheDocument();
    });

    const startButton = screen.getByRole('button', { name: '开始翻译' });
    expect(startButton).toBeEnabled();
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith(
        '/api/translate/start',
        expect.objectContaining({
          api_provider: 'lm_studio',
          model: 'local-model',
          project_id: 'project-cn',
          source_lang_code: 'zh-CN',
          target_lang_codes: ['en'],
        }),
      );
    });
  });

  it('supports select-all and clear while keeping the selected count visible', async () => {
    renderPage();

    await screen.findByRole('button', { name: '请选择目标语言' });
    fireEvent.click(screen.getByRole('button', { name: '全选' }));

    expect(await screen.findByText('已选择 2 种语言')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Français' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: '清除' }));

    expect(await screen.findByText('尚未选择目标语言')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '请选择目标语言' })).toBeDisabled();
  });
});
