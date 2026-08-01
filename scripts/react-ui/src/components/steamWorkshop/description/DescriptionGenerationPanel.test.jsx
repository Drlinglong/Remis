import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';

import api from '../../../utils/api';
import { DescriptionGenerationPanel } from './DescriptionGenerationPanel';

vi.mock('../../../utils/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const configuredProviders = [
  {
    value: 'lm_studio',
    label: 'LM Studio',
    available_models: ['google/gemma-4-31b-qat'],
    selected_model: 'google/gemma-4-31b-qat',
  },
];

const configuredLanguages = {
  zh: { code: 'zh-CN', name: '简体中文' },
};

function getSelectInput(label) {
  return screen.getAllByLabelText(label).find((element) => element.tagName === 'INPUT');
}

describe('DescriptionGenerationPanel', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          data: { api_providers: configuredProviders, languages: configuredLanguages },
        });
      }
      return Promise.resolve({
        data: [{ id: 'lm_studio', is_keyless: true, has_key: false }],
      });
    });
  });

  it('requires explicit approval before sending a model request', async () => {
    const onGenerate = vi.fn().mockResolvedValue({ version_id: 'version-1' });
    render(
      <MantineProvider>
        <DescriptionGenerationPanel
          isGenerating={false}
          onGenerate={onGenerate}
          workshopItemId="3538617386"
        />
      </MantineProvider>,
    );

    await waitFor(() => {
      expect(getSelectInput('API 供应商')).toHaveValue('LM Studio');
      expect(getSelectInput('模型')).toHaveValue('google/gemma-4-31b-qat');
      expect(getSelectInput('描述语言')).toHaveValue('简体中文');
    });

    fireEvent.click(screen.getByRole('button', { name: '模型生成' }));
    const confirm = await screen.findByRole('button', { name: '确认生成' });
    expect(confirm).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', {
      name: '我确认执行这次模型调用，并将结果保存为候选版本',
    }));
    expect(confirm).toBeEnabled();

    fireEvent.click(confirm);

    expect(onGenerate).toHaveBeenCalledWith(expect.objectContaining({
      approved: true,
      model: 'google/gemma-4-31b-qat',
      provider: 'lm_studio',
    }));
  });

  it('explains when no API provider has been configured', async () => {
    api.get.mockImplementation((url) => Promise.resolve({
      data: url === '/api/config'
        ? { api_providers: [], languages: configuredLanguages }
        : [],
    }));

    render(
      <MantineProvider>
        <DescriptionGenerationPanel
          isGenerating={false}
          onGenerate={vi.fn()}
          workshopItemId="3538617386"
        />
      </MantineProvider>,
    );

    expect(await screen.findByText('尚未配置 API 供应商')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '模型生成' })).toBeDisabled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows a retryable error when config loading fails', async () => {
    let configAttempts = 0;
    api.get.mockImplementation((url) => {
      if (url === '/api/api-keys') {
        return Promise.resolve({ data: [] });
      }
      configAttempts += 1;
      return configAttempts === 1
        ? Promise.reject(new Error('offline'))
        : Promise.resolve({
          data: { api_providers: configuredProviders, languages: configuredLanguages },
        });
    });

    render(
      <MantineProvider>
        <DescriptionGenerationPanel
          isGenerating={false}
          onGenerate={vi.fn()}
          workshopItemId="3538617386"
        />
      </MantineProvider>,
    );

    expect(await screen.findByText('API 配置读取失败')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    await waitFor(() => {
      expect(screen.queryByText('API 配置读取失败')).not.toBeInTheDocument();
      expect(getSelectInput('模型')).toHaveValue('google/gemma-4-31b-qat');
    });
  });

  it('blocks a remote provider whose API key is missing', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          data: {
            api_providers: [{
              value: 'anthropic',
              label: 'Anthropic',
              available_models: ['claude-sonnet'],
              selected_model: 'claude-sonnet',
            }],
            languages: configuredLanguages,
          },
        });
      }
      return Promise.resolve({
        data: [{ id: 'anthropic', is_keyless: false, has_key: false }],
      });
    });

    render(
      <MantineProvider>
        <DescriptionGenerationPanel
          isGenerating={false}
          onGenerate={vi.fn()}
          workshopItemId="3538617386"
        />
      </MantineProvider>,
    );

    expect(await screen.findByText('尚未配置 API 密钥')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '模型生成' })).toBeDisabled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
