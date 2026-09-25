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

  it('lets the user explicitly disable inherited reasoning for an unverified selected model', () => {
    const onChange = vi.fn();
    render(
      <MantineProvider>
        <ProviderReasoningSettings
          reasoning={{ supported: false, available_presets: [] }}
          form={{
            reasoningBuiltinEnabled: true,
            reasoningPreset: 'high',
            customParametersText: '{"custom":true}',
          }}
          onChange={onChange}
        />
      </MantineProvider>,
    );

    const toggle = screen.getByRole('switch');
    expect(toggle).toBeChecked();
    expect(toggle).toBeEnabled();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith({ reasoningBuiltinEnabled: false });
    expect(screen.getByDisplayValue('{"custom":true}')).toBeInTheDocument();
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

  it('uses a localized label for the valid none preset', () => {
    const onChange = vi.fn();
    render(
      <MantineProvider>
        <ProviderReasoningSettings
          reasoning={{ supported: true, available_presets: ['none'] }}
          form={{ reasoningBuiltinEnabled: true, reasoningPreset: 'none', customParametersText: '' }}
          onChange={onChange}
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getAllByLabelText('api_reasoning_preset_label').find((element) => element.tagName === 'INPUT'));
    expect(screen.getByRole('option', { name: 'api_reasoning_preset_none' })).toBeInTheDocument();
  });

  it('accepts only JSON objects for custom request parameters', () => {
    expect(parseCustomParameters('{"thinking":{"type":"enabled"}}')).toEqual({
      thinking: { type: 'enabled' },
    });
    expect(() => parseCustomParameters('[]')).toThrow('api_custom_parameters_object_error');
  });
});
