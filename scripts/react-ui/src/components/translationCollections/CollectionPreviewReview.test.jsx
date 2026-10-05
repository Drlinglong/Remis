import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it } from 'vitest';
import { CollectionPreviewReview } from './CollectionPreviewReview';

const t = (key, values) => values ? `${key}:${values.count}` : key;

describe('CollectionPreviewReview', () => {
  it('shows selected files, changed member names, and explicit mutually exclusive conflicts', () => {
    render(<MantineProvider><CollectionPreviewReview
      projects={[{ project_id: 'p1', name: 'Project One' }, { project_id: 'p2', name: 'Project Two' }]}
      t={t}
      inspection={{
        can_export: true, mode: 'portable_translations', file_count: 2, entry_count: 1, runtime_verified: false,
        members: [{ project_id: 'p1', outputs: [{ language_code: 'en', output_folder_name: 'en_out', files: [{ path: 'localisation/key.yml' }] }] }],
        changes: { added: ['p1'], removed: ['p2'], selection_changed: [], content_changed: ['p1'] },
        conflicts: [{ language_code: 'en', key: 'KEY', projects: ['p1', 'p2'], source_conflict: false, translation_conflict: true }],
        diagnostics: [],
      }}
    /></MantineProvider>);
    expect(screen.getByText('localisation/key.yml')).toBeInTheDocument();
    expect(screen.getAllByText(/Project One \(p1\)/)).toHaveLength(3);
    expect(screen.getAllByText(/Project Two \(p2\)/)).toHaveLength(2);
    expect(screen.getByText('translation_collections.paradox_conflicts_instruction')).toBeInTheDocument();
    expect(screen.getByText('KEY')).toBeInTheDocument();
  });
});
