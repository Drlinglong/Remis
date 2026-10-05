import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';
import { CollectionDetails } from './CollectionDetails';

vi.mock('./CollectionMembersEditor', () => ({ CollectionMembersEditor: ({ draftDirty }) => (
  <div>members editor{draftDirty ? <span>translation_collections.unsaved_changes</span> : null}</div>
) }));
const t = (key) => key;

function renderDetails(overrides = {}) {
  const apiState = {
    busy: false, projectOptions: {}, preview: { plan_id: 'p', inspection: { can_export: true, diagnostics: [], mode: 'bundle', file_count: 2, entry_count: 4 } }, history: [],
    loadProjectOptions: vi.fn(), save: vi.fn(), bindPublication: vi.fn(), plan: vi.fn(), exportPackage: vi.fn(), remove: vi.fn(), invalidatePreview: vi.fn(),
    ...overrides,
  };
  render(<MantineProvider><CollectionDetails collection={{ collection_id: 'c1', game_id: 'stellaris', title: 'Collection', target_languages: [] }} projects={[]} languages={[]} apiState={apiState} t={t} /></MantineProvider>);
  return apiState;
}

describe('CollectionDetails', () => {
  it('requires a fresh preview and explicit approval before export', () => {
    const apiState = renderDetails();
    const exportButton = screen.getByRole('button', { name: 'translation_collections.export' });
    expect(exportButton).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: 'translation_collections.approve_export' }));
    expect(exportButton).toBeEnabled();
    fireEvent.click(exportButton);
    expect(apiState.exportPackage).toHaveBeenCalledOnce();
  });

  it('keeps export disabled when inspection blocks the plan', () => {
    renderDetails({ preview: { plan_id: 'p', inspection: { can_export: false, diagnostics: [{ code: 'missing', severity: 'error', message: 'Missing output' }] } } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'translation_collections.approve_export' }));
    expect(screen.getByRole('button', { name: 'translation_collections.export' })).toBeDisabled();
    expect(screen.getByText('Missing output')).toBeInTheDocument();
  });

  it('requires saving edited collection fields before preview or publication changes', () => {
    renderDetails({ draftDirty: true });
    expect(screen.getByText('translation_collections.unsaved_changes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'translation_collections.preview' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'translation_collections.remove_publication' })).toBeDisabled();
  });

  it('allows an explicit publication binding removal', () => {
    const apiState = renderDetails();
    const input = screen.getByLabelText('translation_collections.steam_id');
    fireEvent.change(input, { target: { value: '12345' } });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'translation_collections.remove_publication' }));
    expect(apiState.bindPublication).toHaveBeenCalledWith('');
  });

  it('requires conflict-specific acknowledgment before export', () => {
    renderDetails({ preview: { plan_id: 'conflict-plan', inspection: { can_export: true, conflicts: [{ language_code: 'en', key: 'KEY', projects: ['p1', 'p2'] }] } } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'translation_collections.approve_export' }));
    expect(screen.getByRole('button', { name: 'translation_collections.export' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: 'translation_collections.acknowledge_conflicts' }));
    expect(screen.getByRole('button', { name: 'translation_collections.export' })).toBeEnabled();
  });
});
