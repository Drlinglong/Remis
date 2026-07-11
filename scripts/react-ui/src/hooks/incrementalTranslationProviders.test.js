import { describe, expect, it } from 'vitest';

import {
  buildEmbeddedWorkshopSelection,
  buildProviderSelection,
  resolveProviderModels,
} from './incrementalTranslationProviders';

describe('incrementalTranslationProviders', () => {
  const providers = [
    {
      value: 'gemini',
      available_models: ['gemini-1.5-pro'],
      custom_models: ['gemini-custom'],
      selected_model: 'gemini-selected',
      default_model: 'gemini-default',
    },
    {
      value: 'ollama',
      available_models: ['llama3'],
    },
  ];

  it('merges available, custom, selected, and default models in priority order', () => {
    expect(resolveProviderModels(providers, 'gemini')).toEqual([
      'gemini-default',
      'gemini-selected',
      'gemini-1.5-pro',
      'gemini-custom',
    ]);
  });

  it('builds a provider selection with preferred model and concurrency', () => {
    expect(buildProviderSelection({
      providers,
      providerValue: 'gemini',
      preferredModel: 'gemini-custom',
      preferredConcurrency: 6,
    })).toEqual({
      concurrencyLimit: '6',
      models: ['gemini-default', 'gemini-selected', 'gemini-1.5-pro', 'gemini-custom'],
      selectedModel: 'gemini-custom',
      selectedProvider: 'gemini',
    });
  });

  it('falls back to the first model and local-provider concurrency defaults', () => {
    expect(buildProviderSelection({
      providers,
      providerValue: 'ollama',
      preferredModel: 'missing-model',
    })).toEqual({
      concurrencyLimit: '1',
      models: ['llama3'],
      selectedModel: 'llama3',
      selectedProvider: 'ollama',
    });
  });

  it('selects embedded workshop defaults when independent settings have no provider yet', () => {
    expect(buildEmbeddedWorkshopSelection({
      providers,
      currentProvider: '',
      currentModel: '',
      followPrimary: false,
    })).toEqual({
      selectedProvider: 'gemini',
      selectedModel: 'gemini-default',
    });
  });

  it('keeps embedded workshop settings quiet when following primary settings', () => {
    expect(buildEmbeddedWorkshopSelection({
      providers,
      currentProvider: 'ollama',
      currentModel: 'llama3',
      followPrimary: true,
    })).toBeNull();
  });

  it('repairs stale embedded workshop models for the selected provider', () => {
    expect(buildEmbeddedWorkshopSelection({
      providers,
      currentProvider: 'ollama',
      currentModel: 'missing',
      followPrimary: false,
    })).toEqual({
      selectedProvider: 'ollama',
      selectedModel: 'llama3',
    });
  });
});
