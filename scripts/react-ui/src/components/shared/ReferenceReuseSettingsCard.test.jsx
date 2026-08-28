import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ReferenceReuseSettingsCard from './ReferenceReuseSettingsCard';

const t = (key) => key;

const renderCard = (overrides = {}) => {
  const props = {
    enabled: true,
    onEnabledChange: vi.fn(),
    t,
    ...overrides,
  };
  render(
    <MantineProvider>
      <ReferenceReuseSettingsCard {...props} />
    </MantineProvider>,
  );
  return props;
};

describe('ReferenceReuseSettingsCard', () => {
  it('renders enabled by default and sends the controlled toggle', () => {
    const props = renderCard();
    const toggle = screen.getByRole('switch', { name: /translation_config\.reference_reuse/ });

    expect(toggle).toBeChecked();
    fireEvent.click(toggle);

    expect(props.onEnabledChange).toHaveBeenCalledWith(false);
  });

  it('previews exact matches and lets the user deselect one', () => {
    const onPreview = vi.fn();
    const onToggleEntry = vi.fn();
    renderCard({
      onPreview,
      onToggleEntry,
      previewEntries: [{
        file_path: 'localization/english/countries.yml',
        key: 'TRK:0',
        source_text: 'Turkana',
        target_text: '图尔卡纳',
        target_lang_code: 'zh-CN',
      }],
    });

    fireEvent.click(screen.getByRole('button', { name: 'translation_config.reference_preview' }));
    fireEvent.click(screen.getByRole('checkbox', { name: /TRK:0/ }));

    expect(onPreview).toHaveBeenCalledOnce();
    expect(onToggleEntry).toHaveBeenCalledWith(expect.objectContaining({ key: 'TRK:0' }), false);
  });
});
