import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEditorContent } from './useEditorContent';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';
import {
  PROOFREADING_SESSION_KEY,
  writeProofreadingSession,
} from './proofreadingSession';

vi.mock('../utils/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_key, options) => options?.defaultValue || _key }),
}));

const responseData = (overrides = {}) => ({
  file_path: 'J:/demo/localization/simp_chinese/demo_l_simp_chinese.yml',
  document_revision: 'revision-1',
  rows: [
    {
      entry_id: 'structure-comment-1-2',
      row_type: 'structure',
      structure_type: 'comment',
      line_start: 2,
      line_end: 3,
      source_value: '# Source note',
      final_value: '# Saved note',
      editable: true,
    },
    {
      entry_id: 'entry-0',
      row_type: 'translation',
      key: 'demo.key:0',
      source_value: 'Original',
      ai_value: 'Translation',
      final_value: 'Translation',
      editable: true,
    },
  ],
  ...overrides,
});

describe('useEditorContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    api.get.mockResolvedValue({ data: responseData() });
  });

  it('loads entry rows as the canonical document baseline', async () => {
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    expect(api.get).toHaveBeenCalledWith('/api/proofread/project-1/file-1');
    expect(result.current.documentRevision).toBe('revision-1');
    expect(result.current.rows[1].baseline_value).toBe('Translation');
    expect(result.current.isDirty).toBe(false);
  });

  it('updates a translation row and settles every baseline after save', async () => {
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    act(() => result.current.updateRowFinalValue('entry-0', 'Edited translation'));
    expect(result.current.isDirty).toBe(true);
    expect(result.current.translationChangeCount).toBe(1);
    expect(result.current.getRowsAsSaveEntries()).toEqual([
      { key: 'demo.key:0', value: 'Edited translation' },
    ]);

    act(() => result.current.settleSavedRows('revision-2', true));
    expect(result.current.documentRevision).toBe('revision-2');
    expect(result.current.rows[1].baseline_value).toBe('Edited translation');
    expect(result.current.isDirty).toBe(false);
  });

  it('can discard comment edits while settling saved translation edits', async () => {
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    act(() => {
      result.current.updateRowFinalValue('structure-comment-1-2', '# Edited note');
      result.current.updateRowFinalValue('entry-0', 'Edited translation');
    });
    expect(result.current.commentChangeCount).toBe(1);

    act(() => result.current.settleSavedRows('revision-2', false));
    expect(result.current.rows[0].final_value).toBe('# Saved note');
    expect(result.current.rows[1].final_value).toBe('Edited translation');
    expect(result.current.isDirty).toBe(false);
  });

  it('restores session patches only when the file revision matches', async () => {
    writeProofreadingSession({
      projectId: 'project-1',
      fileId: 'file-1',
      documentRevision: 'revision-1',
      patches: [{
        entry_id: 'entry-0',
        key: 'demo.key:0',
        row_type: 'translation',
        final_value: 'Restored draft',
      }],
    });
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    expect(result.current.rows[1].final_value).toBe('Restored draft');
    expect(result.current.draftRestoreStatus).toBe('restored');
    expect(result.current.isDirty).toBe(true);
  });

  it('reports a session conflict without applying stale patches', async () => {
    writeProofreadingSession({
      projectId: 'project-1',
      fileId: 'file-1',
      documentRevision: 'old-revision',
      patches: [{
        entry_id: 'entry-0',
        key: 'demo.key:0',
        row_type: 'translation',
        final_value: 'Stale draft',
      }],
    });
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    expect(result.current.rows[1].final_value).toBe('Translation');
    expect(result.current.draftRestoreStatus).toBe('conflict');
    expect(result.current.draftConflict).not.toBeNull();
    expect(sessionStorage.getItem(PROOFREADING_SESSION_KEY)).not.toBeNull();
  });

  it('ignores an obsolete failed request after a newer file has loaded', async () => {
    let rejectObsoleteRequest;
    api.get
      .mockImplementationOnce(() => new Promise((_resolve, reject) => {
        rejectObsoleteRequest = reject;
      }))
      .mockResolvedValueOnce({ data: responseData({ file_path: 'J:/demo/new-file.yml', rows: [] }) });

    const { result } = renderHook(() => useEditorContent());
    let obsoleteLoad;
    act(() => { obsoleteLoad = result.current.loadEditorData('project-old', 'file-old'); });
    await act(async () => result.current.loadEditorData('project-new', 'file-new'));
    await act(async () => {
      rejectObsoleteRequest({ response: { status: 404, data: { detail: 'Not found' } } });
      await obsoleteLoad;
    });

    expect(result.current.fileInfo).toEqual({
      path: 'J:/demo/new-file.yml',
      project_id: 'project-new',
      file_id: 'file-new',
    });
    expect(notifications.show).not.toHaveBeenCalled();
  });

  it('detects a newer disk revision even when the local document is clean', async () => {
    api.get.mockImplementation((url) => {
      if (url.endsWith('/revision')) {
        return Promise.resolve({ data: { document_revision: 'revision-2' } });
      }
      return Promise.resolve({ data: responseData() });
    });
    const { result } = renderHook(() => useEditorContent());
    await act(async () => result.current.loadEditorData('project-1', 'file-1'));

    expect(result.current.isDirty).toBe(false);
    await act(async () => result.current.checkExternalRevision());

    expect(api.get).toHaveBeenCalledWith('/api/proofread/project-1/file-1/revision');
    expect(result.current.externalChangeDetected).toEqual({
      loadedRevision: 'revision-1',
      diskRevision: 'revision-2',
    });
  });
});
