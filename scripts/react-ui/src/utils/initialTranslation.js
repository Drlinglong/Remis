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

export function buildTranslationDetails(values, selectedProject, languages = {}) {
  return {
    modName: selectedProject?.label,
    provider: values.api_provider,
    model: values.model_name,
    sourceLang: findLanguageByCode(languages, values.source_lang_code)?.name,
    targetLangs: values.english_disguise
      ? ['Custom (Disguise)']
      : values.target_lang_codes.map((code) => findLanguageByCode(languages, code)?.name),
    gameId: selectedProject?.game_id,
  };
}

export function buildTranslationPayload(values, selectedProjectId) {
  const payload = {
    project_id: selectedProjectId,
    source_lang_code: values.source_lang_code,
    api_provider: values.api_provider,
    model: values.model_name,
    mod_context: values.mod_context,
    selected_glossary_ids: values.selected_glossary_ids,
    use_main_glossary: values.use_main_glossary,
    clean_source: values.clean_source,
    use_resume: values.use_resume,
    batch_size_limit: values.translation_batch_size_limit ? Number(values.translation_batch_size_limit) : null,
    concurrency_limit: values.translation_concurrency_limit ? Number(values.translation_concurrency_limit) : null,
    rpm_limit: values.translation_rpm_limit ? Number(values.translation_rpm_limit) : null,
    embedded_workshop: {
      enabled: values.embedded_workshop_enabled,
      follow_primary_settings: values.embedded_workshop_follow_primary_settings,
      api_provider: values.embedded_workshop_follow_primary_settings ? null : values.embedded_workshop_api_provider,
      api_model: values.embedded_workshop_follow_primary_settings ? null : values.embedded_workshop_api_model,
      batch_size_limit: Number(values.embedded_workshop_batch_size_limit || 10),
      concurrency_limit: Number(values.embedded_workshop_concurrency_limit || 1),
      rpm_limit: Number(values.embedded_workshop_rpm_limit || 40),
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
    payload.target_lang_codes = values.target_lang_codes;
  }

  return payload;
}
