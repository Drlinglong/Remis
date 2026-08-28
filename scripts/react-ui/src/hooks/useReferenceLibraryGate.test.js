import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationService from '../services/translationService';
import { useReferenceLibraryGate } from './useReferenceLibraryGate';

vi.mock('../services/translationService', () => ({
  default: { getReferenceLibraryStatus: vi.fn() },
}));

describe('useReferenceLibraryGate', () => {
  beforeEach(() => vi.clearAllMocks());

  it('prompts only when the selected game has no active library', async () => {
    translationService.getReferenceLibraryStatus.mockResolvedValue({
      data: { libraries: [{ game_id: 'victoria3', available: false }] },
    });
    const { result } = renderHook(() => useReferenceLibraryGate({
      enabled: true,
      explicitPath: '',
      gameId: 'victoria3',
    }));

    await act(async () => expect(await result.current.check()).toBe(true));
    expect(result.current.promptOpen).toBe(true);
  });

  it('marks this run bypassed before continuing', async () => {
    const continuation = vi.fn();
    const { result } = renderHook(() => useReferenceLibraryGate({
      enabled: true,
      explicitPath: '',
      gameId: 'victoria3',
    }));

    act(() => result.current.continueWithoutReference(continuation));

    expect(result.current.bypassed).toBe(true);
    expect(continuation).toHaveBeenCalledOnce();
  });
});
