import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useEditorContent } from './useEditorContent';
import api from '../utils/api';
import { notifications } from '@mantine/notifications';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@mantine/notifications', () => ({
  notifications: {
    show: vi.fn(),
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key, options) => options?.defaultValue || _key,
  }),
}));

vi.mock('./usePersistentState', async () => {
  const ReactModule = await vi.importActual('react');
  return {
    usePersistentState: (_key, initialValue) => ReactModule.useState(initialValue),
  };
});

describe('useEditorContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.post.mockResolvedValue({ data: { content: 'l_english:\n demo.key:0 "Original"\n' } });
    api.get.mockResolvedValue({
      data: {
        file_path: 'J:/demo/localization/simp_chinese/demo_l_simp_chinese.yml',
        entries: [
          {
            key: 'demo.key:0',
            original: 'Original',
            translation: 'Translation',
          },
        ],
        rows: [
          {
            entry_id: 'line-0',
            row_type: 'structure',
            structure_type: 'header',
            display_text: 'l_english:',
          },
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
          },
        ],
      },
    });
  });

  it('does not warn when untouched generated final content keeps versioned keys', async () => {
    const { result } = renderHook(() => useEditorContent());

    await act(async () => {
      await result.current.loadEditorData(
        'project-1',
        'J:/demo/localization/english/demo_l_english.yml',
        'file-1',
      );
    });

    await waitFor(() => {
      expect(result.current.finalContentStr).toContain('demo.key:0 "Translation"');
      expect(result.current.rows).toHaveLength(3);
      expect(result.current.keyChangeWarning).toBe(false);
    });
  });

  it('updates row final values and returns translation rows for saving', async () => {
    const { result } = renderHook(() => useEditorContent());

    await act(async () => {
      await result.current.loadEditorData(
        'project-1',
        'J:/demo/localization/english/demo_l_english.yml',
        'file-1',
      );
    });

    act(() => {
      result.current.updateRowFinalValue('entry-0', 'Edited translation');
    });

    expect(result.current.getRowsAsSaveEntries()).toEqual([
      { key: 'demo.key:0', value: 'Edited translation' },
    ]);
  });

  it('tracks editable comment blocks separately from translation entries', async () => {
    const { result } = renderHook(() => useEditorContent());

    await act(async () => {
      await result.current.loadEditorData(
        'project-1',
        'J:/demo/localization/english/demo_l_english.yml',
        'file-1',
      );
    });

    act(() => {
      result.current.updateRowFinalValue('structure-comment-1-2', '# Edited note');
    });

    expect(result.current.commentChangeCount).toBe(1);
    expect(result.current.getStructurePatches()).toEqual([
      {
        entry_id: 'structure-comment-1-2',
        line_start: 2,
        line_end: 3,
        content: '# Edited note',
      },
    ]);

    act(() => {
      result.current.settleStructureChanges(false);
    });

    expect(result.current.commentChangeCount).toBe(0);
  });

  it('ignores an obsolete failed request after a newer file has loaded', async () => {
    let rejectObsoleteRequest;
    api.get
      .mockImplementationOnce(() => new Promise((_resolve, reject) => {
        rejectObsoleteRequest = reject;
      }))
      .mockResolvedValueOnce({
        data: {
          file_path: 'J:/demo/new-file.yml',
          entries: [],
          rows: [],
          final_content: 'l_simp_chinese:\n new.key:0 "New"\n',
          ai_content: 'l_simp_chinese:\n new.key:0 "New"\n',
        },
      });

    const { result } = renderHook(() => useEditorContent());
    let obsoleteLoad;

    act(() => {
      obsoleteLoad = result.current.loadEditorData('project-old', 'J:/old.yml', 'file-old');
    });

    await act(async () => {
      await result.current.loadEditorData('project-new', 'J:/new.yml', 'file-new');
    });

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

  it('does not compare full final file keys against only translatable entries', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        file_path: 'J:/demo/localization/simp_chinese/demo_l_simp_chinese.yml',
        entries: [
          {
            key: 'translated.key:0',
            original: 'Original',
            translation: 'Translation',
          },
        ],
        ai_content: 'l_simp_chinese:\n translated.key:0 "Translation"\n skipped.variable:0 "$VALUE$"\n',
        final_content: 'l_simp_chinese:\n translated.key:0 "Translation"\n skipped.variable:0 "$VALUE$"\n',
      },
    });

    const { result } = renderHook(() => useEditorContent());

    await act(async () => {
      await result.current.loadEditorData(
        'project-1',
        'J:/demo/localization/english/demo_l_english.yml',
        'file-1',
      );
    });

    await waitFor(() => {
      expect(result.current.finalContentStr).toContain('skipped.variable:0 "$VALUE$"');
      expect(result.current.keyChangeWarning).toBe(false);
    });
  });

  it('warns after the user changes a key from the loaded final file baseline', async () => {
    const { result } = renderHook(() => useEditorContent());

    await act(async () => {
      await result.current.loadEditorData(
        'project-1',
        'J:/demo/localization/english/demo_l_english.yml',
        'file-1',
      );
    });

    act(() => {
      result.current.setFinalContentStr('l_simp_chinese:\n renamed.key:0 "Translation"\n');
    });

    await waitFor(() => {
      expect(result.current.keyChangeWarning).toBe(true);
    });
  });

  it('parses versioned and unversioned localization keys without changing key identity', () => {
    const { result } = renderHook(() => useEditorContent());

    expect(result.current.parseEditorContentToEntries(`
l_simp_chinese:
 demo.key:0 "Translation"
 plain.key: "Plain"
`)).toEqual([
      { key: 'demo.key:0', value: 'Translation' },
      { key: 'plain.key', value: 'Plain' },
    ]);
  });
});
