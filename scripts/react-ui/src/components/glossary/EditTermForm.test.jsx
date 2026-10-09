import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('shows a pending term and saves a human confirmation through the existing editor', async () => {
    const onSave = vi.fn().mockResolvedValue(true);
    renderForm({ selectedTargetLang: 'zh-TW', onSave, selectedTerm: {
      ...selectedTerm, source: 'Idiot', translations: { 'zh-TW': '笨蛋', 'zh-CN': '愚蠢' },
      metadata: { custom: 'preserve me', terminology: {
        locale: 'zh-TW', concept_id: 'mars:trait:6652', source_id: '6652',
        sense: 'Trait tone', context_keys: ['source_id:6652'], review_state: 'pending', confidence: 'low',
        original_candidate: '笨蛋', audit_reason: 'Tone requires a decision', evidence_refs: [{ id: '6652' }],
        historical_reference: { source_id: '6652', english: 'Idiot', translation: '愚蠢' },
      } },
    } });
    expect(screen.getByText('glossary_terminology.pending_note')).toBeInTheDocument();
    expect(screen.getAllByText(/愚蠢/)).toHaveLength(2);
    fireEvent.change(screen.getByDisplayValue('笨蛋'), { target: { value: '愚鈍' } });
    fireEvent.click(screen.getByRole('textbox', { name: 'glossary_terminology.state' }));
    fireEvent.click(await screen.findByRole('option', { name: 'glossary_terminology.states.approved' }));
    fireEvent.click(screen.getByRole('button', { name: 'button_save' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce());
    const saved = onSave.mock.calls[0][0];
    expect(saved.translations).toEqual({ 'zh-TW': '愚鈍', 'zh-CN': '愚蠢' });
    expect(saved.metadata.terminology.review_state).toBe('approved');
    expect(saved.metadata.terminology.review_basis.translation).toBe('愚鈍');
    expect(saved.metadata.terminology.evidence_refs).toEqual([{ id: '6652' }]);
    expect(saved.metadata.custom).toBe('preserve me');
  });
});
