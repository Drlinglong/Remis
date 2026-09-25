export function normalizeCopilotSettings(settings, providers = []) {
  const provider = providers.find((item) => item.id === settings?.provider);
  const hasVerifiedMapping = Boolean(provider?.reasoning_models?.[settings?.model]);
  return {
    ...settings,
    reasoning_enabled: Boolean(settings?.reasoning_enabled && hasVerifiedMapping),
  };
}

export function applyReasoningToggle(event, setForm, presets) {
  const reasoningEnabled = event.currentTarget.checked;
  setForm((current) => ({
    ...current,
    reasoning_enabled: reasoningEnabled,
    reasoning_preset: presets.includes(current.reasoning_preset)
      ? current.reasoning_preset
      : presets[0] || 'medium',
  }));
}
