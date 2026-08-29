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
