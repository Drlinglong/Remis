import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import useGlossaryActions from './useGlossaryActions';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@mantine/notifications', () => ({
  notifications: {
    show: vi.fn(),
  },
}));

const persistentStateStore = new Map();

vi.mock('./usePersistentState', async () => {
  const ReactModule = await vi.importActual('react');
  return {
    usePersistentState: (key, initialValue) => {
      const initial = persistentStateStore.has(key)
        ? persistentStateStore.get(key)
        : initialValue;
      const [value, setValue] = ReactModule.useState(initial);
      const wrappedSetValue = (next) => {
        setValue((prev) => {
          const resolved = typeof next === 'function' ? next(prev) : next;
          persistentStateStore.set(key, resolved);
          return resolved;
        });
      };
      return [value, wrappedSetValue];
    },
  };
});

describe('useGlossaryActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    persistentStateStore.clear();
    api.get.mockImplementation((url) => {
      if (url === '/api/glossary/tree') {
        return Promise.resolve({
          data: [
            {
              key: 'vic3',
              title: 'Victoria 3',
              children: [{ key: 'vic3|7|units.json', title: 'units.json', isLeaf: true }],
            },
          ],
        });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          data: {
            languages: {
              en: { code: 'en', name_local: 'English' },
              zh: { code: 'zh-CN', name_local: '中文' },
            },
          },
        });
      }
      if (url.startsWith('/api/glossary/content')) {
        return Promise.resolve({
          data: {
            entries: [],
            totalCount: 0,
          },
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  });

  it('loads initial tree/config data and picks default game plus target language', async () => {
    const { result } = renderHook(() => useGlossaryActions());

    await waitFor(() => {
      expect(result.current.isLoadingTree).toBe(false);
    });

    expect(result.current.treeData).toHaveLength(1);
    expect(result.current.selectedGame).toBe('vic3');
    expect(result.current.selectedTargetLang).toBe('zh-CN');
    expect(result.current.data).toEqual([]);
  });

  it('selects a leaf node and resets glossary browsing state', async () => {
    const { result } = renderHook(() => useGlossaryActions());

    await waitFor(() => {
      expect(result.current.selectedGame).toBe('vic3');
    });

    act(() => {
      result.current.setSearchScope('all');
      result.current.setFiltering('old');
      result.current.setPagination({ pageIndex: 2, pageSize: 100 });
    });

    await act(async () => {
      result.current.onSelectTree('vic3|7|units.json', { isLeaf: true });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.selectedFile).toEqual({
        key: 'vic3|7|units.json',
        title: 'units.json',
        gameId: 'vic3',
        glossaryId: 7,
      });
    });
    expect(result.current.searchScope).toBe('file');
    expect(result.current.filtering).toBe('');
    expect(result.current.pagination).toEqual({ pageIndex: 0, pageSize: 25 });
  });

  it('creates a glossary file and refreshes the tree', async () => {
    api.post.mockResolvedValue({ data: { ok: true } });

    const { result } = renderHook(() => useGlossaryActions());

    await waitFor(() => {
      expect(result.current.selectedGame).toBe('vic3');
    });

    let success;
    await act(async () => {
      success = await result.current.handleCreateFile('new_terms.json');
    });

    expect(success).toBe(true);
    expect(api.post).toHaveBeenCalledWith('/api/glossary/file', {
      game_id: 'vic3',
      file_name: 'new_terms.json',
    });
    expect(api.get).toHaveBeenCalledWith('/api/glossary/tree');
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'green' })
    );
  });
});
