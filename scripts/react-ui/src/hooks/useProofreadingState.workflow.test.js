import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import useProofreadingState from './useProofreadingState';
import api from '../utils/api';

const settleSavedRows = vi.fn();
const editorState = {
  rows: [{
    entry_id: 'entry-0',
    row_type: 'translation',
    key: 'demo.key:0',
    editable: true,
    baseline_value: '[ROOT]',
    final_value: '[ROOT.GetName]',
  }],
  fileInfo: { project_id: 'project-1', file_id: 'file-1', path: 'J:/demo.yml' },
  documentRevision: 'revision-1',
  draftConflict: null,
  isDirty: true,
  commentChangeCount: 0,
  translationChangeCount: 1,
  getRowsAsSaveEntries: vi.fn(() => [{ key: 'demo.key:0', value: '[ROOT.GetName]' }]),
  getStructurePatches: vi.fn(() => []),
  settleSavedRows,
  updateRowFinalValue: vi.fn(),
  discardCurrentDraft: vi.fn(),
  dismissDraftConflict: vi.fn(),
  loadEditorData: vi.fn(),
  clearEditorData: vi.fn(),
};

vi.mock('./useFileNavigation', () => ({
  useFileNavigation: () => ({
    projects: [{ project_id: 'project-1' }],
    selectedProject: { project_id: 'project-1', source_language: 'english', game_id: 'vic3' },
    currentSourceFile: { file_id: 'source-1' },
    currentTargetFile: { file_id: 'file-1' },
    searchParams: new URLSearchParams(),
    handleProjectSelect: vi.fn(),
  }),
}));

vi.mock('./useEditorContent', () => ({ useEditorContent: () => editorState }));
vi.mock('../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: key => key }) }));

describe('useProofreadingState workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('shows variable changes as an advisory warning, then saves with the loaded revision', async () => {
    api.post.mockResolvedValue({ data: { status: 'success', document_revision: 'revision-2' } });
    const { result } = renderHook(() => useProofreadingState());

    act(() => result.current.requestSave());
    expect(result.current.saveModalOpen).toBe(true);
    expect(result.current.variableWarnings).toHaveLength(1);
    expect(api.post).not.toHaveBeenCalled();

    await act(async () => result.current.confirmSave(true));
    expect(api.post).toHaveBeenCalledWith('/api/proofread/save', expect.objectContaining({
      project_id: 'project-1',
      file_id: 'file-1',
      base_revision: 'revision-1',
    }));
    expect(settleSavedRows).toHaveBeenCalledWith('revision-2', true);
  });

  it('attaches validation results to the entry key represented by the returned line', async () => {
    api.post.mockResolvedValue({
      data: [{ level: 'warning', message: 'Issue', line_number: 1 }],
    });
    const { result } = renderHook(() => useProofreadingState());

    await act(async () => result.current.handleValidate());
    await waitFor(() => expect(result.current.validationResults).toHaveLength(1));
    expect(result.current.validationResults[0].key).toBe('demo.key:0');
  });
});
