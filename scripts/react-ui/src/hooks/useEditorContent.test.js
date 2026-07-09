import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useEditorContent } from './useEditorContent';
import api from '../utils/api';

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
      expect(result.current.keyChangeWarning).toBe(false);
    });
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
