import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';
import { CollectionMembersEditor } from './CollectionMembersEditor';

describe('collection member output ownership', () => {
  it('restores saved selections and only changes the clicked member', () => {
    const oldOutput = { language_code: 'fr', output_folder_name: 'fr-original' };
    const newOutput = { language_code: 'fr', output_folder_name: 'fr-new' };
    const collection = { title: 'Bundle', game_id: 'stellaris', target_languages: ['fr'],
      members: ['a', 'b'].map((project_id) => ({ project_id, outputs: [oldOutput] })) };
    const onSave = vi.fn();
    render(<MantineProvider><CollectionMembersEditor
      collection={collection} projects={[]} languages={[{ value: 'fr', label: 'French' }]}
      optionsByProject={{ a: { translation_outputs: [oldOutput] }, b: { translation_outputs: [oldOutput, newOutput] } }}
      optionsLoading={{}} onLoadOptions={vi.fn()} onSave={onSave} onEdit={vi.fn()} t={(key) => key}
    /></MantineProvider>);
    const selected = screen.getAllByRole('checkbox', { name: 'fr · fr-original' });
    expect(selected[0]).toBeChecked();
    expect(selected[1]).toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: 'fr · fr-new' }));
    expect(selected[0]).toBeChecked();
    expect(selected[1]).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'translation_collections.save_members' }));
    expect(onSave.mock.calls[0][0].members).toEqual([
      { project_id: 'a', outputs: [oldOutput] }, { project_id: 'b', outputs: [newOutput] },
    ]);
  });
});
