import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../../utils/api';
import { useDescriptionModelConfig } from './useDescriptionModelConfig';

vi.mock('../../../utils/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('useDescriptionModelConfig', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('uses the same selected/default/available/custom model preference as initial translation', async () => {
    api.get.mockImplementation((url) => Promise.resolve({ data: url === '/api/config' ? {
      api_providers: [
        {
          value: 'lm_studio',
          label: 'LM Studio',
          available_models: ['fallback-local'],
          custom_models: ['custom-local'],
          selected_model: 'google/gemma-4-31b-qat',
        },
        {
          value: 'openai',
          label: 'OpenAI',
          available_models: ['gpt-5-mini'],
          default_model: 'gpt-5',
          selected_model: 'gpt-5',
        },
      ],
    } : [] }));

    const { result } = renderHook(() => useDescriptionModelConfig());

    await waitFor(() => {
      expect(result.current.provider).toBe('lm_studio');
      expect(result.current.model).toBe('google/gemma-4-31b-qat');
    });
    expect(result.current.modelOptions.map((item) => item.value)).toEqual([
      'google/gemma-4-31b-qat',
      'fallback-local',
      'custom-local',
    ]);

    act(() => result.current.setProvider('openai'));

    await waitFor(() => {
      expect(result.current.model).toBe('gpt-5');
    });
  });

  it('clears the model and exposes an empty model list for an unconfigured provider', async () => {
    api.get.mockImplementation((url) => Promise.resolve({
      data: url === '/api/config' ? {
        api_providers: [{
          value: 'custom_provider',
          label: 'Custom Provider',
        }],
      } : [],
    }));

    const { result } = renderHook(() => useDescriptionModelConfig());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.provider).toBe('custom_provider');
    });
    expect(result.current.model).toBe('');
    expect(result.current.modelOptions).toEqual([]);
  });
});
