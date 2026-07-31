import React from 'react';
import { fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../../utils/api';
import { DescriptionGenerationPanel } from './DescriptionGenerationPanel';
import { useDescriptionModelConfig } from './useDescriptionModelConfig';

vi.mock('../../../utils/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const languageConfig = {
  en: { code: 'en', name: 'English' },
  zh: { code: 'zh-CN', name: '简体中文' },
  fr: { code: 'fr', name: 'Français' },
  de: { code: 'de', name: 'Deutsch' },
  es: { code: 'es', name: 'Español' },
  ja: { code: 'ja', name: '日本語' },
  ko: { code: 'ko', name: '한국어' },
  pl: { code: 'pl', name: 'Polski' },
  pt: { code: 'pt-BR', name: 'Português do Brasil' },
  ru: { code: 'ru', name: 'Русский' },
  tr: { code: 'tr', name: 'Türkçe' },
};

const configuredProvider = {
  value: 'lm_studio',
  label: 'LM Studio',
  available_models: ['google/gemma-4-31b-qat'],
  selected_model: 'google/gemma-4-31b-qat',
};

const keylessStatus = [{ id: 'lm_studio', is_keyless: true, has_key: false }];

function mockApi({ providers = [configuredProvider], statuses = keylessStatus } = {}) {
  api.get.mockImplementation((url) => Promise.resolve({
    data: url === '/api/config'
      ? { api_providers: providers, languages: languageConfig }
      : statuses,
  }));
}

function renderPanel({ onGenerate = vi.fn(), workshopItemId = '3538617386' } = {}) {
  return render(
    <MantineProvider>
      <DescriptionGenerationPanel
        isGenerating={false}
        onGenerate={onGenerate}
        workshopItemId={workshopItemId}
      />
    </MantineProvider>,
  );
}

function getSelectInput(label) {
  return screen.getAllByLabelText(label).find((element) => element.tagName === 'INPUT');
}

describe('DescriptionGenerationPanel outer configuration regression', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('keeps provider, model, and the eleven configured languages on the main page', async () => {
    mockApi();
    renderPanel();

    await waitFor(() => {
      expect(getSelectInput('API 供应商')).toHaveValue('LM Studio');
      expect(getSelectInput('模型')).toHaveValue('google/gemma-4-31b-qat');
      expect(getSelectInput('描述语言')).toHaveValue('简体中文');
    });

    expect(screen.getByText('使用该语言来生成创意工坊描述')).toBeInTheDocument();
    expect(getSelectInput('描述语言')).toHaveAttribute('aria-haspopup', 'listbox');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('derives all eleven language options from the config response', async () => {
    mockApi();
    const { result } = renderHook(() => useDescriptionModelConfig());

    await waitFor(() => expect(result.current.languageOptions).toHaveLength(11));
    expect(result.current.languageOptions).toEqual(
      Object.values(languageConfig).map(({ code, name }) => ({ value: code, label: name })),
    );
  });

  it('keeps only the call summary and explicit approval inside the modal', async () => {
    mockApi();
    renderPanel();

    await waitFor(() => expect(screen.getByRole('button', { name: '模型生成' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: '模型生成' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog.closest('[data-remis-surface="elevated"]')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-header')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-title')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-body')).toBeInTheDocument();
    expect(within(dialog).getByText('本次调用摘要')).toBeInTheDocument();
    expect(within(dialog).getByText('LM Studio')).toBeInTheDocument();
    expect(within(dialog).getByText('google/gemma-4-31b-qat')).toBeInTheDocument();
    expect(within(dialog).getByText('简体中文')).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('API 供应商')).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText('模型')).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText('描述语言')).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText('发布模板')).not.toBeInTheDocument();
    expect(within(dialog).getByRole('checkbox', {
      name: '我确认执行这次模型调用，并将结果保存为候选版本',
    })).toBeInTheDocument();
    expect(screen.queryByText(/并发|RPM/)).not.toBeInTheDocument();
  });

  it('shows an explicit loading state before configuration is available', async () => {
    let resolveConfig;
    api.get.mockImplementation((url) => (
      url === '/api/config'
        ? new Promise((resolve) => { resolveConfig = resolve; })
        : Promise.resolve({ data: keylessStatus })
    ));
    renderPanel();

    expect(await screen.findByText('正在读取 API 配置')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '模型生成' })).toBeDisabled();

    resolveConfig({ data: { api_providers: [configuredProvider], languages: languageConfig } });
    await waitFor(() => expect(getSelectInput('描述语言')).toHaveValue('简体中文'));
  });

  it.each([
    {
      name: 'no provider',
      providers: [],
      statuses: [],
      message: '尚未配置 API 供应商',
    },
    {
      name: 'no model',
      providers: [{ value: 'local', label: 'Local', available_models: [] }],
      statuses: [{ id: 'local', is_keyless: true, has_key: false }],
      message: '当前供应商没有可用模型',
    },
    {
      name: 'missing key',
      providers: [{ ...configuredProvider, value: 'openai', label: 'OpenAI' }],
      statuses: [{ id: 'openai', is_keyless: false, has_key: false }],
      message: '尚未配置 API 密钥',
    },
  ])('keeps the $name state visible on the main page', async ({ message, providers, statuses }) => {
    mockApi({ providers, statuses });
    renderPanel();

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '模型生成' })).toBeDisabled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
