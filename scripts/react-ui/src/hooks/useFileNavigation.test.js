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

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParamsValue, setSearchParamsMock],
}));

vi.mock('../utils/fileGrouping', () => ({
  groupFiles: vi.fn((files) => {
    const source = files.find(file => file.file_path.includes('_l_english'));
    const target = files.find(file => file.file_path.includes('_l_simp_chinese'));
    return {
      sources: source ? [source] : [],
      targetsMap: source && target ? { [source.file_id]: [target] } : {},
    };
  }),
}));

describe('useFileNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
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
            {
              project_id: 'proj-2',
              name: 'Second Project',
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

    expect(result.current.projects).toHaveLength(2);
    expect(result.current.currentTargetFile).toEqual({
      file_id: 'target-1',
      file_path: 'events_l_simp_chinese.yml',
    });
  });

  it('updates URL params when selecting a project manually', async () => {
    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.projects).toHaveLength(2);
    });

    act(() => {
      result.current.handleProjectSelect('proj-1');
    });

    expect(setSearchParamsMock).toHaveBeenCalledWith({ projectId: 'proj-1' });
  });

  it('preserves the source task while switching proofreading files', async () => {
    searchParamsValue = new URLSearchParams(
      'projectId=proj-1&fileId=target-1&taskId=task-origin',
    );
    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.selectedProject?.project_id).toBe('proj-1');
    });

    act(() => {
      result.current.handleSourceFileChange('source-1');
    });

    expect(setSearchParamsMock).toHaveBeenCalledWith({
      projectId: 'proj-1',
      fileId: 'target-1',
      taskId: 'task-origin',
    });
  });

  it('clears the previous project files before loading the newly selected project', async () => {
    let resolveSecondProject;
    api.get.mockImplementation((url) => {
      if (url === '/api/projects?status=active') {
        return Promise.resolve({
          data: [
            { project_id: 'proj-1', name: 'Demo Project', source_language: 'english' },
            { project_id: 'proj-2', name: 'Second Project', source_language: 'english' },
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
      if (url === '/api/project/proj-2/files') {
        return new Promise(resolve => {
          resolveSecondProject = resolve;
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    const { result } = renderHook(() => useFileNavigation());

    await waitFor(() => {
      expect(result.current.currentTargetFile?.file_id).toBe('target-1');
    });

    act(() => {
      result.current.handleProjectSelect('proj-2');
    });

    expect(result.current.selectedProject?.project_id).toBe('proj-2');
    expect(result.current.currentSourceFile).toBeNull();
    expect(result.current.currentTargetFile).toBeNull();

    await act(async () => {
      resolveSecondProject({ data: [] });
    });
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
