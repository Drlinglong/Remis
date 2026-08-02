import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ProviderReasoningSettings from './ProviderReasoningSettings';
import { parseCustomParameters } from './reasoningForm';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

describe('ProviderReasoningSettings', () => {
  it('keeps unverified models opt-in safe while preserving custom JSON', () => {
    const onChange = vi.fn();
    render(
      <MantineProvider>
        <ProviderReasoningSettings
          reasoning={{ supported: false, available_presets: [] }}
          form={{
            reasoningBuiltinEnabled: false,
            reasoningPreset: 'medium',
            customParametersText: '{"think": true}',
          }}
          onChange={onChange}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('api_reasoning_unverified')).toBeInTheDocument();
    expect(screen.getByRole('switch')).toBeDisabled();
    expect(screen.getByDisplayValue('{"think": true}')).toBeInTheDocument();
  });

  it('allows toggling a verified provider-native preset', () => {
    const onChange = vi.fn();
    render(
      <MantineProvider>
        <ProviderReasoningSettings
          reasoning={{ supported: true, available_presets: ['low', 'high'] }}
          form={{
            reasoningBuiltinEnabled: true,
            reasoningPreset: 'low',
            customParametersText: '',
          }}
          onChange={onChange}
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith({ reasoningBuiltinEnabled: false });
  });

  it('accepts only JSON objects for custom request parameters', () => {
    expect(parseCustomParameters('{"thinking":{"type":"enabled"}}')).toEqual({
      thinking: { type: 'enabled' },
    });
    expect(() => parseCustomParameters('[]')).toThrow('api_custom_parameters_object_error');
  });
});
