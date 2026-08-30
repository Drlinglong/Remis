export const TRANSLATION_CONTEXT_MODES = Object.freeze({
  NONE: 'none',
  GLOSSARIES: 'glossaries',
  ARCHIVE: 'archive',
});

export function resolveTranslationContextMode(values = {}) {
  const validModes = new Set(Object.values(TRANSLATION_CONTEXT_MODES));
  if (validModes.has(values.translation_context_mode)) {
    return values.translation_context_mode;
  }
  return values.use_main_glossary === false
    ? TRANSLATION_CONTEXT_MODES.NONE
    : TRANSLATION_CONTEXT_MODES.ARCHIVE;
}

export function normalizeProjects(projects = []) {
  return projects.map((project) => ({
    value: project.project_id,
    label: project.name,
    game_id: project.game_id,
    source_language: project.source_language,
  }));
}

export function normalizeAvailableGlossaries(glossaries = []) {
  return glossaries
    .filter((glossary) => !glossary.is_main)
    .map((glossary) => ({
      value: String(glossary.glossary_id),
      label: glossary.name,
    }));
}

export function findProjectById(projects = [], projectId) {
  return projects.find((project) => project.value === projectId) || null;
}

export function findLanguageByCode(languages = {}, code) {
  return Object.values(languages).find((language) => language.code === code) || null;
}

export function findLanguageByKey(languages = {}, key) {
  return Object.values(languages).find((language) => language.key === key) || null;
}

export function resolveGameProfile(gameProfiles = {}, gameId) {
  return gameProfiles[gameId] || Object.values(gameProfiles).find((profile) => profile.id === gameId) || null;
}

export function resolveGameName(gameProfiles = {}, gameId) {
  const profile = resolveGameProfile(gameProfiles, gameId);
  return profile ? profile.name.split('(')[0].trim() : 'Unknown';
}

export function filterProjects(projects = [], gameFilter, searchQuery) {
  const normalizedQuery = (searchQuery || '').toLowerCase();
  return projects.filter((project) => {
    const matchesGame = gameFilter === 'all' || !gameFilter || project.game_id === gameFilter;
    const matchesSearch = project.label.toLowerCase().includes(normalizedQuery);
    return matchesGame && matchesSearch;
  });
}

export function getTargetLangCodes(values) {
  return values.english_disguise ? ['custom'] : values.target_lang_codes;
}

export function buildModelOptions(providerValue, apiProviders = []) {
  const providerConfig = apiProviders.find((provider) => provider.value === providerValue);
  if (!providerConfig) {
    return [];
  }

  let models = [];
  const availableModelsList = providerConfig.available_models || [];
  const customModelsList = providerConfig.custom_models || [];
  const combinedModels = [...new Set([...availableModelsList, ...customModelsList])];

  if (combinedModels.length > 0) {
    models = combinedModels.map((model) => {
      const isCustom = customModelsList.includes(model) && !availableModelsList.includes(model);
      return {
        value: model,
        label: isCustom ? `${model} (Custom)` : model,
      };
    });
  }

  if (providerConfig.default_model && !models.some((model) => model.value === providerConfig.default_model)) {
    models.unshift({ value: providerConfig.default_model, label: providerConfig.default_model });
  }

  if (providerConfig.selected_model && !models.some((model) => model.value === providerConfig.selected_model)) {
    models.unshift({ value: providerConfig.selected_model, label: providerConfig.selected_model });
  }

  if (models.length === 0) {
    if (providerValue === 'gemini') {
      models = [
        { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
        { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro Preview' },
      ];
    } else if (providerValue === 'ollama') {
      models = [
        { value: 'qwen3:4b', label: 'Qwen 3 (4B)' },
        { value: 'qwen2.5:7b', label: 'Qwen 2.5 (7B)' },
        { value: 'llama3', label: 'Llama 3' },
      ];
    }
  }

  return models;
}

export function resolvePreferredModel(models = [], currentModelName, selectedModelName) {
  const currentModelValid = models.some((model) => model.value === currentModelName);

  if (selectedModelName && models.some((model) => model.value === selectedModelName)) {
    if (!currentModelValid || !currentModelName) {
      return selectedModelName;
    }
  }

  if (!currentModelValid && models.length > 0) {
    return models[0].value;
  }

  if (models.length === 0) {
    return '';
  }

  return currentModelName;
}

export function resolveProjectSourceLanguage(values, selectedProject) {
  return selectedProject?.source_language || values.source_lang_code;
}

export function buildTranslationDetails(values, selectedProject, languages = {}) {
  const sourceLangCode = resolveProjectSourceLanguage(values, selectedProject);
  const disguiseLanguage = findLanguageByKey(languages, values.custom_key);
  const customTargetLabel = `${values.custom_name || 'Custom'} (disguised as ${disguiseLanguage?.name || values.custom_key || 'Unknown'})`;
  return {
    projectId: selectedProject?.value,
    modName: selectedProject?.label,
    provider: values.api_provider,
    model: values.model_name,
    sourceLang: findLanguageByCode(languages, sourceLangCode)?.name,
    targetLangs: values.english_disguise
      ? [customTargetLabel]
      : values.target_lang_codes.map((code) => findLanguageByCode(languages, code)?.name),
    gameId: selectedProject?.game_id,
  };
}

export function buildTranslationPayload(values, selectedProjectId, selectedProject = null) {
  const sourceLangCode = resolveProjectSourceLanguage(values, selectedProject);
  const translationContextMode = resolveTranslationContextMode(values);
  const useGlossaries = translationContextMode !== TRANSLATION_CONTEXT_MODES.NONE;
  const payload = {
    project_id: selectedProjectId,
    source_lang_code: sourceLangCode,
    api_provider: values.api_provider,
    model: values.model_name,
    mod_context: values.mod_context,
    selected_glossary_ids: useGlossaries ? values.selected_glossary_ids : [],
    translation_context_mode: translationContextMode,
    use_main_glossary: useGlossaries,
    use_project_context: translationContextMode === TRANSLATION_CONTEXT_MODES.ARCHIVE,
    clean_source: values.clean_source,
    use_resume: values.use_resume,
    reference_reuse: {
      enabled: values.reference_reuse_enabled !== false,
      localization_path: values.reference_localization_path || '',
      excluded_entries: values.reference_reuse_excluded_entries || [],
    },
    batch_size_limit: values.translation_batch_size_limit ? Number(values.translation_batch_size_limit) : null,
    concurrency_limit: values.translation_concurrency_limit ? Number(values.translation_concurrency_limit) : null,
    rpm_limit: values.translation_rpm_limit ? Number(values.translation_rpm_limit) : null,
    embedded_workshop: {
      enabled: values.embedded_workshop_enabled,
      follow_primary_settings: values.embedded_workshop_follow_primary_settings,
      api_provider: values.embedded_workshop_follow_primary_settings ? null : values.embedded_workshop_api_provider,
      api_model: values.embedded_workshop_follow_primary_settings ? null : values.embedded_workshop_api_model,
      batch_size_limit: values.embedded_workshop_follow_primary_settings
        ? (values.translation_batch_size_limit ? Number(values.translation_batch_size_limit) : null)
        : Number(values.embedded_workshop_batch_size_limit || 10),
      concurrency_limit: values.embedded_workshop_follow_primary_settings
        ? (values.translation_concurrency_limit ? Number(values.translation_concurrency_limit) : null)
        : Number(values.embedded_workshop_concurrency_limit || 1),
      rpm_limit: values.embedded_workshop_follow_primary_settings
        ? (values.translation_rpm_limit ? Number(values.translation_rpm_limit) : null)
        : Number(values.embedded_workshop_rpm_limit || 40),
    },
  };

  if (values.english_disguise) {
    payload.custom_lang_config = {
      name: values.custom_name,
      code: 'custom',
      key: values.custom_key,
      folder_prefix: values.custom_prefix,
    };
    payload.target_lang_codes = ['custom'];
  } else {
    payload.target_lang_codes = (values.target_lang_codes || []).filter((code) => code !== sourceLangCode);
  }

  return payload;
}
