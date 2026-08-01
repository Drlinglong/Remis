import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import i18n from '../../../i18n/i18n';

import { FEATURES } from '../../../config/features';
import api from '../../../utils/api';
import {
  buildModelOptions,
  resolvePreferredModel,
} from '../../../utils/initialTranslation';

function visibleProviders(apiProviders = []) {
  return apiProviders.filter(
    (provider) => provider.value !== 'hunyuan' || FEATURES.ENABLE_HUNYUAN_PROVIDER,
  );
}

export function useDescriptionModelConfig() {
  const [apiProviders, setApiProviders] = useState([]);
  const [languages, setLanguages] = useState({});
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [providerStatuses, setProviderStatuses] = useState([]);
  const [loadError, setLoadError] = useState('');
  const requestIdRef = useRef(0);

  const loadConfig = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setIsLoading(true);
    setLoadError('');

    try {
      const [configResult, statusResult] = await Promise.allSettled([
        api.get('/api/config'),
        api.get('/api/api-keys'),
      ]);
      if (requestId !== requestIdRef.current) return;
      if (configResult.status !== 'fulfilled') {
        throw configResult.reason;
      }
      const providers = Array.isArray(configResult.value.data?.api_providers)
        ? configResult.value.data.api_providers
        : [];
      const configuredLanguages = configResult.value.data?.languages;
      setApiProviders(visibleProviders(providers));
      setLanguages(
        configuredLanguages && typeof configuredLanguages === 'object'
          ? configuredLanguages
          : {},
      );
      setProviderStatuses(
        statusResult.status === 'fulfilled' && Array.isArray(statusResult.value.data)
          ? statusResult.value.data
          : [],
      );
    } catch {
      if (requestId !== requestIdRef.current) return;
      setApiProviders([]);
      setLanguages({});
      setProviderStatuses([]);
      setLoadError(i18n.t('steam_workshop.api_configuration_unavailable'));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadConfig();
    return () => {
      requestIdRef.current += 1;
    };
  }, [loadConfig]);

  const providerOptions = useMemo(
    () => apiProviders.map((item) => ({ value: item.value, label: item.label })),
    [apiProviders],
  );

  const languageOptions = useMemo(
    () => Object.values(languages)
      .filter((item) => item && item.code)
      .map((item) => ({
        value: item.code,
        label: item.name || item.name_en || item.code,
      })),
    [languages],
  );

  useEffect(() => {
    const providerIsAvailable = apiProviders.some((item) => item.value === provider);
    if (!providerIsAvailable) {
      setProvider(apiProviders[0]?.value || '');
    }
  }, [apiProviders, provider]);

  const modelOptions = useMemo(
    () => buildModelOptions(provider, apiProviders),
    [apiProviders, provider],
  );

  useEffect(() => {
    const providerConfig = apiProviders.find((item) => item.value === provider);
    const preferredModel = resolvePreferredModel(
      modelOptions,
      model,
      providerConfig?.selected_model,
    );
    if (preferredModel !== model) {
      setModel(preferredModel);
    }
  }, [apiProviders, model, modelOptions, provider]);

  const selectedProviderStatus = providerStatuses.find((item) => item.id === provider);
  const missingApiKey = Boolean(
    selectedProviderStatus
    && !selectedProviderStatus.is_keyless
    && !selectedProviderStatus.has_key,
  );

  return {
    isLoading,
    languageOptions,
    loadConfig,
    loadError,
    model,
    modelOptions,
    missingApiKey,
    provider,
    providerOptions,
    setModel,
    setProvider,
  };
}
