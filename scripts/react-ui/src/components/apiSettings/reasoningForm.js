export const parseCustomParameters = (value) => {
  const trimmed = value.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('api_custom_parameters_object_error');
  }
  return parsed;
};

export const selectReasoningModel = (form, selectedModel, reasoningModels = {}) => {
  const capability = reasoningModels[selectedModel];
  const presets = Object.keys(capability?.presets || {});
  const nextPreset = capability && !presets.includes(form.reasoningPreset)
    ? (presets[0] || 'medium')
    : form.reasoningPreset;
  return {
    ...form,
    selectedModel: selectedModel || '',
    reasoningBuiltinEnabled: capability ? form.reasoningBuiltinEnabled : false,
    reasoningPreset: nextPreset,
  };
};

export const isReasoningSelectionValid = (form, reasoningModels = {}) => {
  if (!form.reasoningBuiltinEnabled) return true;
  return Boolean(reasoningModels[form.selectedModel]?.presets?.[form.reasoningPreset]);
};

export const shouldEnableBuiltinReasoning = (form, reasoningModels = {}) => (
  Boolean(form.reasoningBuiltinEnabled && isReasoningSelectionValid(form, reasoningModels))
);
