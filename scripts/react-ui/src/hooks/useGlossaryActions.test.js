import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
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

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => {
      if (key === 'glossary_health_queued_ai_plan') {
        return `Reviewing ${options.count} repair case(s) in ${options.batches} model batch(es).`;
      }
      return ({
        glossary_entry_saved_title: 'Glossary entry saved',
        glossary_entry_saved_message: 'Your glossary change has been saved successfully.',
        glossary_entry_save_failed: 'The glossary entry could not be saved.',
      }[key] || options?.defaultValue || key);
    },
  }),
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
      const wrappedSetValue = ReactModule.useCallback((next) => {
        setValue((prev) => {
          const resolved = typeof next === 'function' ? next(prev) : next;
          persistentStateStore.set(key, resolved);
          return resolved;
        });
      }, [key]);
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
            api_providers: [{
              value: 'lm_studio',
              label: 'LM Studio',
              selected_model: 'local-model',
            }],
          },
        });
      }
      if (url === '/api/glossaries/overview') {
        return Promise.resolve({
          data: {
            summary: {
              game_count: 1,
              glossary_count: 1,
              term_count: 0,
              bound_project_count: 0,
            },
            glossaries: [{
              glossary_id: 7,
              game_id: 'vic3',
              name: 'units.json',
              kind: 'standard',
              entry_count: 0,
              bound_projects: [],
            }],
          },
        });
      }
      if (url === '/api/projects') {
        return Promise.resolve({
          data: [{
            project_id: 'project-1',
            name: 'Victoria Mod',
            game_id: 'vic3',
            status: 'active',
          }],
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

  const renderGlossaryHook = (initialEntries = ['/glossary']) => renderHook(
    () => useGlossaryActions(),
    {
      wrapper: ({ children }) => React.createElement(
        MemoryRouter,
        { initialEntries },
        children
      ),
    }
  );

  it('loads initial tree/config data and picks default game plus target language', async () => {
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.isLoadingTree).toBe(false);
    });

    expect(result.current.treeData).toHaveLength(1);
    expect(result.current.selectedGame).toBe('vic3');
    expect(result.current.selectedTargetLang).toBe('zh-CN');
    expect(result.current.apiProviders).toHaveLength(1);
    expect(result.current.projects).toHaveLength(1);
    expect(result.current.data).toEqual([]);
    expect(result.current.viewMode).toBe('overview');
    expect(result.current.overview.summary.glossary_count).toBe(1);
  });

  it('normalizes wrapped glossary collection payloads at the API boundary', async () => {
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/glossary/tree') {
        return Promise.resolve({
          data: {
            tree: [{
              key: 'vic3',
              title: 'Victoria 3',
              children: [{ key: 'vic3|7|units.json', title: 'units.json', isLeaf: true }],
            }],
          },
        });
      }
      if (url === '/api/glossaries/overview') {
        return Promise.resolve({
          data: {
            overview: {
              summary: { glossary_count: 1 },
              glossaries: [{ glossary_id: 7, game_id: 'vic3', name: 'units.json' }],
            },
          },
        });
      }
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'wrapped-project', name: 'Wrapped' }] },
        });
      }
      return originalGet(url);
    });

    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    expect(result.current.treeData).toHaveLength(1);
    expect(result.current.projects).toEqual([
      expect.objectContaining({ project_id: 'wrapped-project' }),
    ]);
    expect(result.current.overview.glossaries).toEqual([
      expect.objectContaining({ glossary_id: 7 }),
    ]);
  });

  it('selects a leaf node and resets glossary browsing state', async () => {
    const { result } = renderGlossaryHook();

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
    expect(result.current.viewMode).toBe('editor');
  });

  it('localizes the manual glossary-entry save notification', async () => {
    api.post.mockResolvedValue({ data: { id: 'term-1' } });
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.selectedGame).toBe('vic3');
    });
    act(() => {
      result.current.onSelectTree('vic3|7|units.json', { isLeaf: true });
    });

    let success;
    await act(async () => {
      success = await result.current.handleSave({
        source: '泰尔紫',
        translations: { en: 'Tyrian purple' },
      });
    });

    expect(success).toBe(true);
    expect(notifications.show).toHaveBeenCalledWith({
      title: 'Glossary entry saved',
      message: 'Your glossary change has been saved successfully.',
      color: 'green',
    });
  });

  it('creates a named glossary asset and refreshes the tree', async () => {
    api.post.mockResolvedValue({ data: { ok: true } });

    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.selectedGame).toBe('vic3');
    });

    let success;
    await act(async () => {
      success = await result.current.handleCreateGlossary('Core terminology');
    });

    expect(success).toBe(true);
    expect(api.post).toHaveBeenCalledWith('/api/glossary', {
      game_id: 'vic3',
      name: 'Core terminology',
    });
    expect(api.get).toHaveBeenCalledWith('/api/glossary/tree');
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'green' })
    );
  });

  it('does not report a completed create as failed when the index refresh fails', async () => {
    api.post.mockResolvedValue({ data: { ok: true } });
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.selectedGame).toBe('vic3');
    });

    api.get.mockRejectedValue(new Error('refresh unavailable'));

    let success;
    await act(async () => {
      success = await result.current.handleCreateGlossary('Core terminology');
    });

    expect(success).toBe(true);
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'orange', title: 'Refresh failed' })
    );
  });

  it('duplicates a glossary and refreshes both glossary indexes', async () => {
    api.post.mockResolvedValue({
      data: {
        glossary_id: 8,
        game_id: 'vic3',
        name: 'units review',
        entry_count: 12,
      },
    });
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.isLoadingTree).toBe(false);
    });

    let success;
    await act(async () => {
      success = await result.current.handleDuplicateGlossary(
        { glossary_id: 7, name: 'units.json' },
        ' units review '
      );
    });

    expect(success).toBe(true);
    expect(api.post).toHaveBeenCalledWith('/api/glossary/file/7/duplicate', {
      name: 'units review',
    });
    expect(api.get).toHaveBeenCalledWith('/api/glossary/tree');
    expect(api.get).toHaveBeenCalledWith('/api/glossaries/overview');
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'green', title: 'Glossary duplicated' })
    );
  });

  it('updates glossary information and refreshes both glossary indexes', async () => {
    api.put.mockResolvedValue({
      data: {
        glossary_id: 7,
        game_id: 'vic3',
        name: 'Reviewed Units',
        description: 'Reviewed terminology.',
      },
    });
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.isLoadingTree).toBe(false);
    });

    let success;
    await act(async () => {
      success = await result.current.handleUpdateGlossaryMetadata(
        { glossary_id: 7, name: 'units.json' },
        {
          name: ' Reviewed Units ',
          description: ' Reviewed terminology. ',
          kind: 'project',
          projectIds: ['project-1'],
        }
      );
    });

    expect(success).toBe(true);
    expect(api.put).toHaveBeenCalledWith('/api/glossary/file/7', {
      name: 'Reviewed Units',
      description: 'Reviewed terminology.',
      kind: 'project',
      project_ids: ['project-1'],
    });
    expect(api.get).toHaveBeenCalledWith('/api/glossary/tree');
    expect(api.get).toHaveBeenCalledWith('/api/glossaries/overview');
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'green', title: 'Glossary information updated' })
    );
  });

  it('previews and executes a guarded batch deletion', async () => {
    api.post.mockImplementation((url) => {
      if (url === '/api/glossaries/batch-delete/preview') {
        return Promise.resolve({ data: { glossary_count: 1, term_count: 12 } });
      }
      if (url === '/api/glossaries/batch-delete') {
        return Promise.resolve({
          data: {
            deleted_glossary_count: 1,
            deleted_term_count: 12,
          },
        });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });
    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.isLoadingTree).toBe(false);
    });

    let impact;
    let success;
    await act(async () => {
      impact = await result.current.previewGlossaryBatchDelete([7]);
      success = await result.current.handleBatchDeleteGlossaries([7], {
        mainGlossaries: true,
        projectBindings: false,
      });
    });

    expect(impact).toEqual({ glossary_count: 1, term_count: 12 });
    expect(success).toBe(true);
    expect(api.post).toHaveBeenCalledWith('/api/glossaries/batch-delete/preview', {
      glossary_ids: [7],
    });
    expect(api.post).toHaveBeenCalledWith('/api/glossaries/batch-delete', {
      glossary_ids: [7],
      confirm_main_glossaries: true,
      confirm_project_bindings: false,
    });
  });

  it('previews and starts a merge through the unified task monitor', async () => {
    api.post.mockImplementation((url) => {
      if (url === '/api/glossaries/merge/preview') {
        return Promise.resolve({ data: { unique_term_count: 12, conflict_count: 1 } });
      }
      if (url === '/api/glossaries/merge') {
        return Promise.resolve({
          data: {
            task_id: 'merge-task',
            status: 'queued',
            preview: { unique_term_count: 12, conflict_count: 1 },
          },
        });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/tasks/merge-task') {
        return Promise.resolve({
          data: {
            status: 'completed',
            result: { summary: 'Merge complete', metadata: { glossary_id: 8 } },
          },
        });
      }
      return originalGet(url);
    });
    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    const options = {
      target_mode: 'new',
      target_glossary_id: null,
      target_name: 'Merged',
      conflict_strategy: 'skip_conflicts',
    };
    let preview;
    let started;
    await act(async () => {
      preview = await result.current.previewGlossaryMerge([7, 8], options);
      started = await result.current.startGlossaryMerge([7, 8], options);
    });

    expect(preview.unique_term_count).toBe(12);
    expect(started.task_id).toBe('merge-task');
    await waitFor(() => expect(result.current.glossaryOperation?.status).toBe('completed'));
    expect(api.get).toHaveBeenCalledWith('/api/tasks/merge-task');
  });

  it('starts a read-only health task and exposes its report', async () => {
    api.post.mockResolvedValue({
      data: {
        task_id: 'health-task',
        status: 'queued',
        deterministic_preview: { score: 88, issue_count: 2 },
        ai_advice_requested: false,
      },
    });
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/tasks/health-task') {
        return Promise.resolve({
          data: {
            status: 'completed',
            result: {
              summary: 'Health complete',
              metadata: { score: 88, issue_count: 2, mutations_applied: false },
            },
          },
        });
      }
      return originalGet(url);
    });
    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    await act(async () => {
      await result.current.startGlossaryHealthCheck([7], {
        target_lang: 'zh-CN',
        include_ai_advice: false,
        confirm_model_usage: false,
        api_provider: null,
        model_name: null,
      });
    });

    await waitFor(() => expect(result.current.glossaryOperation?.status).toBe('completed'));
    expect(result.current.glossaryOperation.task.result.metadata.mutations_applied).toBe(false);
  });

  it('reports the dynamic AI batch plan when a health task is queued', async () => {
    api.post.mockResolvedValue({
      data: {
        task_id: 'health-ai-task',
        status: 'queued',
        deterministic_preview: { score: 94, issue_count: 2 },
        ai_advice_requested: true,
        ai_review_plan: {
          case_count: 2,
          batch_count: 1,
          batch_sizes: [2],
        },
      },
    });
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/tasks/health-ai-task') {
        return Promise.resolve({
          data: {
            status: 'completed',
            result: {
              summary: 'Health complete',
              metadata: { score: 94, issue_count: 2, mutations_applied: false },
            },
          },
        });
      }
      return originalGet(url);
    });
    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    await act(async () => {
      await result.current.startGlossaryHealthCheck([7], {
        target_lang: 'en',
        include_ai_advice: true,
        confirm_model_usage: true,
        api_provider: 'lm_studio',
        model_name: 'local-model',
      });
    });

    expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
      message: 'Reviewing 2 repair case(s) in 1 model batch(es).',
      color: 'blue',
    }));
    expect(result.current.glossaryOperation.aiReviewPlan.batch_sizes).toEqual([2]);
  });

  it('reuses an already-active identical health task instead of offering another run', async () => {
    api.post.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: {
            message: 'An identical glossary health check is already active.',
            task_id: 'existing-health-task',
          },
        },
      },
    });
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/tasks/existing-health-task') {
        return Promise.resolve({
          data: {
            status: 'completed',
            result: {
              metadata: { score: 94, issue_count: 2, mutations_applied: false },
            },
          },
        });
      }
      return originalGet(url);
    });
    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    let started;
    await act(async () => {
      started = await result.current.startGlossaryHealthCheck([7], {
        target_lang: 'en',
        include_ai_advice: false,
      });
    });

    expect(started).toEqual(expect.objectContaining({
      task_id: 'existing-health-task',
      existing_task: true,
    }));
    await waitFor(() => expect(result.current.glossaryOperation?.status).toBe('completed'));
  });

  it('resumes a persisted glossary task after the hook remounts', async () => {
    persistentStateStore.set('glossary_active_operation', {
      taskId: 'resumed-health-task',
      kind: 'health',
      status: 'running',
      preview: { score: 90 },
    });
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url) => {
      if (url === '/api/tasks/resumed-health-task') {
        return Promise.resolve({
          data: {
            status: 'completed',
            result: {
              metadata: { score: 92, issue_count: 1, mutations_applied: false },
            },
          },
        });
      }
      return originalGet(url);
    });

    const { result } = renderGlossaryHook();

    await waitFor(() => {
      expect(result.current.glossaryOperation?.status).toBe('completed');
    });
    expect(api.get).toHaveBeenCalledWith('/api/tasks/resumed-health-task');
    expect(result.current.glossaryOperation.task.result.metadata.score).toBe(92);
  });

  it('loads persisted health-check history for one glossary', async () => {
    const originalGet = api.get.getMockImplementation();
    api.get.mockImplementation((url, config) => {
      if (url === '/api/tasks') {
        expect(config.params).toEqual({
          kind: 'glossary_health_check',
          glossary_id: 7,
          include_archived: true,
          limit: 50,
        });
        return Promise.resolve({ data: { tasks: [{ task_id: 'health-old' }] } });
      }
      return originalGet(url);
    });
    const { result } = renderGlossaryHook();
    await waitFor(() => expect(result.current.isLoadingTree).toBe(false));

    let tasks;
    await act(async () => {
      tasks = await result.current.loadGlossaryHealthHistory(7);
    });

    expect(tasks).toEqual([{ task_id: 'health-old' }]);
  });

  it('applies glossary deep links after the tree loads', async () => {
    const { result } = renderGlossaryHook(['/glossary?game_id=vic3&glossary_id=7']);

    await waitFor(() => {
      expect(result.current.selectedFile).toEqual({
        key: 'vic3|7|units.json',
        title: 'units.json',
        gameId: 'vic3',
        glossaryId: 7,
      });
    });

    expect(result.current.selectedGame).toBe('vic3');
    expect(result.current.searchScope).toBe('file');
    expect(result.current.filtering).toBe('');
    expect(result.current.pagination).toEqual({ pageIndex: 0, pageSize: 25 });
    expect(result.current.viewMode).toBe('editor');
  });

  it('focuses a reported entry even when a historical task lacks the game id', async () => {
    api.post.mockResolvedValue({
      data: {
        entries: [{
          id: 'term-42',
          source: 'Army',
          translations: { en: 'Army' },
          notes: '',
        }],
        totalCount: 1,
      },
    });
    const { result } = renderGlossaryHook([
      '/glossary-manager?glossary_id=7&focus_entry_id=term-42&target_lang=en',
    ]);

    await waitFor(() => {
      expect(result.current.selectedFile.glossaryId).toBe(7);
    });

    expect(result.current.selectedGame).toBe('vic3');
    expect(result.current.filtering).toBe('');
    expect(result.current.selectedTargetLang).toBe('en');
    expect(result.current.viewMode).toBe('editor');
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/glossary/search', expect.objectContaining({
        scope: 'file',
        query: 'term-42',
      }));
    });
    await waitFor(() => {
      expect(result.current.focusedEntry).toEqual(expect.objectContaining({
        id: 'term-42',
        source: 'Army',
      }));
    });
  });
});
