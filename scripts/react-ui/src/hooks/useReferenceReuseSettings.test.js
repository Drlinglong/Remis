import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationService from '../services/translationService';
import { useReferenceReuseSettings } from './useReferenceReuseSettings';

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));
vi.mock('../services/translationService', () => ({
  default: { previewReferenceReuse: vi.fn() },
}));

describe('useReferenceReuseSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('clears preview matches and exclusions when their context changes', async () => {
    const match = {
      file_path: 'localization/english/countries.yml',
      key: 'TRK:0',
      source_text: 'Turkana',
      target_lang_code: 'zh-CN',
    };
    translationService.previewReferenceReuse.mockResolvedValue({ data: { matches: [match] } });
    const { result } = renderHook(() => useReferenceReuseSettings((key) => key));

    act(() => result.current.setReferenceLocalizationPath('C:/Victoria 3/game/localization'));
    await act(() => result.current.previewReferenceReuse({
      projectId: 'demo',
      sourceLangCode: 'en',
      sourcePath: 'J:/mod/new-version',
      targetLangCodes: ['zh-CN'],
    }));
    act(() => result.current.toggleReferenceEntry(match, false));

    expect(result.current.referencePreviewEntries).toEqual([match]);
    expect(result.current.referenceReuseExcludedEntries).toHaveLength(1);
    expect(translationService.previewReferenceReuse).toHaveBeenCalledWith(
      expect.objectContaining({ custom_source_path: 'J:/mod/new-version' }),
    );

    act(() => result.current.resetReferencePreview());

    expect(result.current.referencePreviewEntries).toEqual([]);
    expect(result.current.referenceReuseExcludedEntries).toEqual([]);
    expect(result.current.referencePreviewError).toBe('');
  });

  it('ignores a preview response invalidated by a context reset', async () => {
    let resolvePreview;
    translationService.previewReferenceReuse.mockReturnValue(new Promise((resolve) => {
      resolvePreview = resolve;
    }));
    const { result } = renderHook(() => useReferenceReuseSettings((key) => key));
    act(() => result.current.setReferenceLocalizationPath('C:/Victoria 3/game/localization'));

    let pending;
    act(() => {
      pending = result.current.previewReferenceReuse({
        projectId: 'demo', sourceLangCode: 'en', targetLangCodes: ['zh-CN'],
      });
    });
    act(() => result.current.resetReferencePreview());
    await act(async () => {
      resolvePreview({ data: { matches: [{ key: 'STALE' }] } });
      await pending;
    });

    expect(result.current.referencePreviewEntries).toEqual([]);
    expect(result.current.referencePreviewLoading).toBe(false);
  });
});
