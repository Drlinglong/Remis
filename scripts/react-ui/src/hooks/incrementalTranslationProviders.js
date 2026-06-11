import { LOCAL_PROVIDERS } from './incrementalTranslationPayload';

export const resolveProviderModels = (providers = [], providerValue) => {
  const providerData = providers.find((provider) => provider.value === providerValue);
  if (!providerData) return [];

  const availableModels = providerData.available_models || [];
  const customModels = providerData.custom_models || [];
  const merged = [...new Set([...availableModels, ...customModels])];

  if (providerData.selected_model && !merged.includes(providerData.selected_model)) {
    merged.unshift(providerData.selected_model);
  }
  if (providerData.default_model && !merged.includes(providerData.default_model)) {
    merged.unshift(providerData.default_model);
  }

  return merged;
};

export const buildProviderSelection = ({
  providers = [],
  providerValue,
  preferredModel = '',
  preferredConcurrency = null,
  defaultProvider = 'gemini',
} = {}) => {
  const selectedProvider = providerValue || defaultProvider;
  const models = resolveProviderModels(providers, selectedProvider);
  const selectedModel = preferredModel && models.includes(preferredModel)
    ? preferredModel
    : (models[0] || '');
  const concurrencyLimit = preferredConcurrency !== null && preferredConcurrency !== undefined
    ? String(preferredConcurrency)
    : (LOCAL_PROVIDERS.includes(selectedProvider) ? '1' : '10');

  return {
    concurrencyLimit,
    models,
    selectedModel,
    selectedProvider,
  };
};
