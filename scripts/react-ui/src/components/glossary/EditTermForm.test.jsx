import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import EditTermForm from './EditTermForm';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

const targetLanguages = [
  { code: 'zh-CN', name_local: '中文' },
  { code: 'en', name_local: 'English' },
];

const selectedTerm = {
  id: 42,
  source: 'factory',
  translations: {
    'zh-CN': '工厂',
  },
  notes: 'industrial term',
  variants: {
    'zh-CN': ['厂房'],
  },
  abbreviations: {
    en: 'fac.',
  },
  metadata: {
    domain: 'production',
  },
};

const renderForm = (props = {}) => render(
  <MantineProvider>
    <EditTermForm
      selectedTerm={selectedTerm}
      isCreating={false}
      onClose={vi.fn()}
      onSave={vi.fn()}
      targetLanguages={targetLanguages}
      selectedTargetLang="zh-CN"
      isSaving={false}
      {...props}
    />
  </MantineProvider>
);

describe('EditTermForm', () => {
  beforeEach(() => {
    const portal = document.createElement('div');
    portal.id = 'glossary-detail-portal';
    document.body.appendChild(portal);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('hydrates an existing selected term without triggering a render loop', () => {
    renderForm();

    expect(screen.getByDisplayValue('factory')).toBeInTheDocument();
    expect(screen.getByDisplayValue('工厂')).toBeInTheDocument();
    expect(screen.getByDisplayValue('industrial term')).toBeInTheDocument();
  });

  it('updates form values when another term is selected', () => {
    const { rerender } = renderForm();

    rerender(
      <MantineProvider>
        <EditTermForm
          selectedTerm={{
            ...selectedTerm,
            id: 43,
            source: 'railway',
            translations: { 'zh-CN': '铁路' },
            notes: '',
          }}
          isCreating={false}
          onClose={vi.fn()}
          onSave={vi.fn()}
          targetLanguages={targetLanguages}
          selectedTargetLang="zh-CN"
          isSaving={false}
        />
      </MantineProvider>
    );

    expect(screen.getByDisplayValue('railway')).toBeInTheDocument();
    expect(screen.getByDisplayValue('铁路')).toBeInTheDocument();
  });
});
