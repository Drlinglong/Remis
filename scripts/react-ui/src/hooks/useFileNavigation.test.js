import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useFileNavigation } from './useFileNavigation';
import api from '../utils/api';

const setSearchParamsMock = vi.fn();
let searchParamsValue;

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
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

vi.mock('react-router-dom', () => ({
  useSearchParams: () => [searchParamsValue, setSearchParamsMock],
}));

vi.mock('../utils/fileGrouping', () => ({
  groupFiles: vi.fn(() => ({
    sources: [{ file_id: 'source-1', file_path: 'events_l_english.yml' }],
    targetsMap: {
      'source-1': [{ file_id: 'target-1', file_path: 'events_l_simp_chinese.yml' }],
    },
  })),
}));

describe('useFileNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    persistentStateStore.clear();
    searchParamsValue = new URLSearchParams('projectId=proj-1&fileId=target-1');
    api.get.mockImplementation((url) => {
      if (url === '/api/projects?status=active') {
        return Promise.resolve({
          data: [
            {
              project_id: 'proj-1',
              name: 'Demo Project',
              source_language: 'english',
            },
          ],
        });
      }
      if (url === '/api/project/proj-1/files') {
        return Promise.resolve({
          data: [
            { file_id: 'source-1', file_path: 'events_l_english.yml' },
            { file_id: 'target-1', file_path: 'events_l_simp_chinese.yml' },
          ],
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  });

  it('loads projects, resolves project from URL, and picks current source/target file', async () => {
    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.selectedProject?.project_id).toBe('proj-1');
    });

    await waitFor(() => {
      expect(result.current.currentSourceFile?.file_id).toBe('source-1');
    });

    expect(result.current.projects).toHaveLength(1);
    expect(result.current.currentTargetFile).toEqual({
      file_id: 'target-1',
      file_path: 'events_l_simp_chinese.yml',
    });
  });

  it('updates URL params when selecting a project manually', async () => {
    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.projects).toHaveLength(1);
    });

    act(() => {
      result.current.handleProjectSelect('proj-1');
    });

    expect(setSearchParamsMock).toHaveBeenCalledWith({ projectId: 'proj-1' });
  });

  it('switches source file and syncs the chosen target file into URL params', async () => {
    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.selectedProject?.project_id).toBe('proj-1');
    });

    act(() => {
      result.current.handleSourceFileChange('source-1');
    });

    expect(result.current.currentSourceFile?.file_id).toBe('source-1');
    expect(result.current.currentTargetFile?.file_id).toBe('target-1');
    expect(setSearchParamsMock).toHaveBeenCalledWith({
      projectId: 'proj-1',
      fileId: 'target-1',
    });
  });
});
