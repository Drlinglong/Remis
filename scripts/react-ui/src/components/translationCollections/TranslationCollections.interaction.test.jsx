import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../utils/api';
import { useTranslationCollections } from '../../hooks/useTranslationCollections';

vi.mock('../../utils/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

function InteractionHarness() {
  const [opened, setOpened] = useState(true);
  const state = useTranslationCollections(opened);
  return <>
    <button onClick={() => state.create({ title: 'Late create', game_id: 'stellaris', target_languages: ['en'], members: [] })}>Create</button>
    <button onClick={() => { state.close(); setOpened(false); }}>Close</button>
    <button onClick={() => setOpened(true)}>Reopen</button>
    <button onClick={() => state.openCollection('a')}>Open A</button>
    <button onClick={() => state.openCollection('b')}>Open B</button>
    <button onClick={() => state.save({ title: 'A edited', description: '', target_languages: ['en'], members: [] })}>Save current</button>
    <div data-testid="selected">{state.selected?.title || 'none'}</div>
    <div data-testid="collections">{state.collections.map((item) => item.title).join(',')}</div>
  </>;
}

function renderHarness() {
  return render(<MantineProvider><InteractionHarness /></MantineProvider>);
}

describe('translation collection request lifecycle interactions', () => {
  beforeEach(() => vi.resetAllMocks());

  it('ignores a create response after close and reopen', async () => {
    const pendingCreate = deferred();
    api.get.mockResolvedValue({ data: { collections: [] } });
    api.post.mockReturnValue(pendingCreate.promise);
    renderHarness();
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reopen' }));
    pendingCreate.resolve({ data: { collection_id: 'late', title: 'Late create' } });
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('none'));
    expect(screen.getByTestId('collections')).toBeEmptyDOMElement();
  });

  it('does not let a late save for collection A replace selected collection B', async () => {
    const pendingSave = deferred();
    api.get.mockImplementation((url) => {
      if (url.endsWith('/a')) return Promise.resolve({ data: { collection_id: 'a', title: 'Collection A', revision: 1, members: [] } });
      if (url.endsWith('/b')) return Promise.resolve({ data: { collection_id: 'b', title: 'Collection B', revision: 1, members: [] } });
      return Promise.resolve({ data: { exports: [] } });
    });
    api.put.mockReturnValue(pendingSave.promise);
    renderHarness();
    fireEvent.click(screen.getByRole('button', { name: 'Open A' }));
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('Collection A'));
    fireEvent.click(screen.getByRole('button', { name: 'Save current' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole('button', { name: 'Open B' }));
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('Collection B'));
    pendingSave.resolve({ data: { collection_id: 'a', title: 'A edited', revision: 2, members: [] } });
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('Collection B'));
  });
});
