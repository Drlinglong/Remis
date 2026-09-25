import { describe, expect, it } from 'vitest';
import {
  isReasoningSelectionValid,
  selectReasoningModel,
  shouldEnableBuiltinReasoning,
} from './reasoningForm';

const form = {
  selectedModel: 'known-model',
  reasoningBuiltinEnabled: true,
  reasoningPreset: 'high',
  customParametersText: '{"reasoning":{"effort":"high"}}',
};

describe('reasoning model selection', () => {
  it('turns built-in reasoning off for a manual model without changing preset or custom JSON', () => {
    const next = selectReasoningModel(form, 'gpt-6-luna', {
      'known-model': { presets: { low: {}, high: {} } },
    });

    expect(next).toMatchObject({
      selectedModel: 'gpt-6-luna',
      reasoningBuiltinEnabled: false,
      reasoningPreset: 'high',
      customParametersText: form.customParametersText,
    });
    expect(isReasoningSelectionValid(next)).toBe(true);
    expect(shouldEnableBuiltinReasoning(next)).toBe(false);
  });

  it('preserves a selected preset when the new mapping supports it', () => {
    const next = selectReasoningModel(form, 'other-model', {
      'other-model': { presets: { low: { effort: 'low' }, high: { effort: 'high' } } },
    });

    expect(next.reasoningBuiltinEnabled).toBe(true);
    expect(next.reasoningPreset).toBe('high');
    expect(isReasoningSelectionValid(next, {
      'other-model': { presets: { low: { effort: 'low' }, high: { effort: 'high' } } },
    })).toBe(true);
  });

  it('uses the first preset for a mapped model that cannot honor the existing preset', () => {
    const next = selectReasoningModel(form, 'low-only-model', {
      'low-only-model': { presets: { low: { effort: 'low' } } },
    });

    expect(next.reasoningBuiltinEnabled).toBe(true);
    expect(next.reasoningPreset).toBe('low');
    expect(isReasoningSelectionValid(next, {
      'low-only-model': { presets: { low: { effort: 'low' } } },
    })).toBe(true);
    expect(shouldEnableBuiltinReasoning(next, {
      'low-only-model': { presets: { low: { effort: 'low' } } },
    })).toBe(true);
  });

  it('keeps an explicit disabled setting disabled for a known model', () => {
    const next = selectReasoningModel({ ...form, reasoningBuiltinEnabled: false }, 'mapped', {
      mapped: { presets: { low: {} } },
    });

    expect(next.reasoningBuiltinEnabled).toBe(false);
    expect(isReasoningSelectionValid(next, { mapped: { presets: { low: {} } } })).toBe(true);
  });
});
