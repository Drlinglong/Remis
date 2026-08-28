import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useInitialReferenceReuse } from './useInitialReferenceReuse';
import translationService from '../services/translationService';

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));
vi.mock('../services/translationService', () => ({
  default: { previewReferenceReuse: vi.fn() },
}));

describe('useInitialReferenceReuse', () => {
  beforeEach(() => vi.clearAllMocks());

  it('clears preview state when the target-language context changes', async () => {
    const match = { key: 'TRK:0', source_text: 'Turkana', target_text: '图尔卡纳' };
    const setFieldValue = vi.fn();
    translationService.previewReferenceReuse.mockResolvedValue({ data: { matches: [match] } });
    const options = {
      excludedEntries: [],
      localizationPath: 'C:/Victoria 3/game/localization',
      projectId: 'demo',
      setFieldValue,
      sourceLangCode: 'en',
      t: (key) => key,
      targetLangCodes: ['zh-CN'],
    };
    const { result, rerender } = renderHook(
      ({ targetLangCodes }) => useInitialReferenceReuse({ ...options, targetLangCodes }),
      { initialProps: { targetLangCodes: ['zh-CN'] } },
    );

    await act(() => result.current.preview());
    expect(result.current.previewEntries).toEqual([match]);

    rerender({ targetLangCodes: ['fr'] });

    expect(result.current.previewEntries).toEqual([]);
    expect(setFieldValue).toHaveBeenCalledWith('reference_reuse_excluded_entries', []);
  });

  it('ignores a preview response from the previous language context', async () => {
    let resolvePreview;
    translationService.previewReferenceReuse.mockReturnValue(new Promise((resolve) => {
      resolvePreview = resolve;
    }));
    const options = {
      excludedEntries: [],
      localizationPath: 'C:/Victoria 3/game/localization',
      projectId: 'demo',
      setFieldValue: vi.fn(),
      sourceLangCode: 'en',
      t: (key) => key,
    };
    const { result, rerender } = renderHook(
      ({ targetLangCodes }) => useInitialReferenceReuse({ ...options, targetLangCodes }),
      { initialProps: { targetLangCodes: ['zh-CN'] } },
    );

    let pending;
    act(() => { pending = result.current.preview(); });
    rerender({ targetLangCodes: ['fr'] });
    await act(async () => {
      resolvePreview({ data: { matches: [{ key: 'STALE' }] } });
      await pending;
    });

    expect(result.current.previewEntries).toEqual([]);
    expect(result.current.previewLoading).toBe(false);
  });
});
