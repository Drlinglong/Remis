import { useEffect, useRef, useState } from 'react';

import api from '../utils/api';
import notificationService from '../services/notificationService';
import {
  buildModelOptions,
  normalizeAvailableGlossaries,
  normalizeProjects,
  resolvePreferredModel,
} from '../utils/initialTranslation';

function sameModelOptions(left = [], right = []) {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((item, index) => (
    item.value === right[index]?.value && item.label === right[index]?.label
  ));
}

export function useInitialTranslationPageData({ form, notificationStyle, selectedProjectId, t }) {
  const [config, setConfig] = useState({
    game_profiles: {},
    languages: {},
    api_providers: [],
  });
  const [projects, setProjects] = useState([]);
  const [availableModels, setAvailableModels] = useState([]);
  const [availableGlossaries, setAvailableGlossaries] = useState([]);
  const { values } = form;
  const hasLoadedRef = useRef(false);
  const setFieldValueRef = useRef(form.setFieldValue);
  setFieldValueRef.current = form.setFieldValue;
  const selectedGameId = projects.find((project) => project.value === selectedProjectId)?.game_id;

  useEffect(() => {
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;

    Promise.allSettled([
      api.get('/api/config'),
      api.get('/api/projects'),
      api.get('/api/prompts'),
    ])
      .then(([configResult, projectsResult, promptsResult]) => {
        let hasAnySuccess = false;

        if (configResult.status === 'fulfilled') {
          setConfig(configResult.value.data);
          hasAnySuccess = true;
        } else {
          console.error('Failed to load translation config:', configResult.reason);
        }

        if (projectsResult.status === 'fulfilled') {
          setProjects(normalizeProjects(projectsResult.value.data));
          hasAnySuccess = true;
        } else {
          console.error('Failed to load projects:', projectsResult.reason);
        }

        if (promptsResult.status === 'fulfilled') {
          if (promptsResult.value.data.custom_global_prompt) {
            setFieldValueRef.current('mod_context', promptsResult.value.data.custom_global_prompt);
          }
          hasAnySuccess = true;
        } else {
          console.error('Failed to load prompts:', promptsResult.reason);
        }

        if (!hasAnySuccess) {
          notificationService.error(t('message_error_load_config'), notificationStyle);
        }
      })
  }, [notificationStyle, t]);

  useEffect(() => {
    let cancelled = false;

    if (!selectedGameId) {
      setAvailableGlossaries((prev) => (prev.length === 0 ? prev : []));
      if ((values.selected_glossary_ids || []).length > 0) {
        setFieldValueRef.current('selected_glossary_ids', []);
      }
      return undefined;
    }

    api.get(`/api/glossaries/${selectedGameId}`)
      .then((response) => {
        if (cancelled) {
          return;
        }

        const normalizedGlossaries = normalizeAvailableGlossaries(response.data);
        setAvailableGlossaries(normalizedGlossaries);

        const allowedValues = new Set(normalizedGlossaries.map((glossary) => glossary.value));
        const filteredSelectedGlossaries = (values.selected_glossary_ids || [])
          .filter((glossaryId) => allowedValues.has(String(glossaryId)));

        if (filteredSelectedGlossaries.length !== (values.selected_glossary_ids || []).length) {
          setFieldValueRef.current('selected_glossary_ids', filteredSelectedGlossaries);
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        console.error(`Failed to load glossaries for ${selectedGameId}:`, error);
        setAvailableGlossaries([]);
        if ((values.selected_glossary_ids || []).length > 0) {
          setFieldValueRef.current('selected_glossary_ids', []);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedGameId, values.selected_glossary_ids]);

  useEffect(() => {
    const providerConfig = config.api_providers.find((provider) => provider.value === values.api_provider);
    if (!providerConfig) {
      setAvailableModels((prev) => (prev.length === 0 ? prev : []));
      if (values.model_name !== '') {
        setFieldValueRef.current('model_name', '');
      }
      return;
    }

    const models = buildModelOptions(values.api_provider, config.api_providers);
    setAvailableModels((prev) => (sameModelOptions(prev, models) ? prev : models));

    const nextModelName = resolvePreferredModel(
      models,
      values.model_name,
      providerConfig.selected_model,
    );

    if (nextModelName !== values.model_name) {
      setFieldValueRef.current('model_name', nextModelName);
    }
  }, [config.api_providers, values.api_provider, values.model_name]);

  return {
    availableGlossaries,
    availableModels,
    config,
    projects,
  };
}
