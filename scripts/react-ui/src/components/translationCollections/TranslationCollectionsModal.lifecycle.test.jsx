import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../utils/api';
import { TranslationCollectionsModal } from './TranslationCollectionsModal';

vi.mock('../../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key) => key }) }));

const base = '/api/translation-collections';
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const collections = ['a', 'b'].map((id) => ({
  collection_id: id, title: `Collection ${id.toUpperCase()}`, game_id: 'stellaris',
  target_languages: ['en'], revision: 1, members: [{ project_id: 'shared', outputs: [] }],
}));

describe('TranslationCollectionsModal output request lifecycle', () => {
  beforeEach(() => vi.resetAllMocks());

  it('loads shared member outputs after switching and keeps the new request loading when the old one settles', async () => {
    const oldOptions = deferred();
    const currentOptions = deferred();
    let optionsRequests = 0;
    api.get.mockImplementation((url) => {
      if (url === base) return Promise.resolve({ data: { collections } });
      if (url === `${base}/project-options/shared`) {
        optionsRequests += 1;
        return optionsRequests === 1 ? oldOptions.promise : currentOptions.promise;
      }
      const collection = collections.find((item) => url === `${base}/${item.collection_id}`);
      return Promise.resolve({ data: collection || { exports: [] } });
    });
    render(<MantineProvider><TranslationCollectionsModal
      opened onClose={vi.fn()}
      projects={[{ project_id: 'shared', name: 'Shared project', game_id: 'stellaris', status: 'active' }]}
      games={[{ value: 'stellaris', label: 'Stellaris', supported_language_codes: ['en'] }]}
      languages={[{ value: 'en', label: 'English' }]}
    /></MantineProvider>);

    fireEvent.click(await screen.findByRole('button', { name: /^Collection A/ }));
    await waitFor(() => expect(optionsRequests).toBe(1));
    const back = screen.getByRole('button', { name: 'translation_collections.back' });
    await waitFor(() => expect(back).toBeEnabled());
    fireEvent.click(back);
    fireEvent.click(screen.getByRole('button', { name: /^Collection B/ }));
    await waitFor(() => expect(optionsRequests).toBe(2));

    await act(async () => {
      oldOptions.resolve({ data: { translation_outputs: [{ language_code: 'en', output_folder_name: 'en-old' }] } });
      await oldOptions.promise;
    });
    expect(screen.queryByRole('checkbox', { name: 'en · en-old' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'translation_collections.refresh_outputs' })).toHaveAttribute('data-loading');

    await act(async () => {
      currentOptions.resolve({ data: { translation_outputs: [{ language_code: 'en', output_folder_name: 'en-current' }] } });
      await currentOptions.promise;
    });
    expect(await screen.findByRole('checkbox', { name: 'en · en-current' })).toBeEnabled();
    expect(screen.getByText('Collection B')).toBeInTheDocument();
    expect(optionsRequests).toBe(2);
  });
});
