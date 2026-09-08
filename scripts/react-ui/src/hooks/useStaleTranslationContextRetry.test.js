import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  STALE_DISABLE_ARCHIVE,
  STALE_USE_OLD_ARCHIVE,
} from '../services/translationContextStaleService';
import { useStaleTranslationContextRetry } from './useStaleTranslationContextRetry';

const staleError = (hash, release = 'release-1') => ({
  response: {
    status: 409,
    data: {
      detail: {
        code: 'context_release_stale_choice_required',
        context_readiness: {
          archive: {
            release_id: release,
            current_source_snapshot_hash: hash,
          },
        },
      },
    },
  },
});

const payload = { project_id: 'demo', translation_context_mode: 'archive' };

describe('useStaleTranslationContextRetry', () => {
  it('retries with an acknowledgement for the selected archive choice', async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(staleError('hash-1'))
      .mockResolvedValueOnce({ data: { task_id: 'task-1' } });
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useStaleTranslationContextRetry());

    await act(async () => {
      await result.current.submit({ payload, request, onSuccess });
    });
    expect(result.current.opened).toBe(true);

    await act(async () => {
      await result.current.choose(STALE_USE_OLD_ARCHIVE);
    });

    expect(request).toHaveBeenLastCalledWith({
      ...payload,
      stale_choice: STALE_USE_OLD_ARCHIVE,
      stale_acknowledgement: {
        choice: STALE_USE_OLD_ARCHIVE,
        context_release_id: 'release-1',
        source_snapshot_hash: 'hash-1',
      },
    });
    expect(onSuccess).toHaveBeenCalledWith({ data: { task_id: 'task-1' } });
    expect(result.current.opened).toBe(false);
  });

  it('uses the newest source hash when a retry is stale again', async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(staleError('hash-1'))
      .mockRejectedValueOnce(staleError('hash-2'))
      .mockResolvedValueOnce({ data: { task_id: 'task-2' } });
    const { result } = renderHook(() => useStaleTranslationContextRetry());

    await act(async () => {
      await result.current.submit({ payload, request, onSuccess: vi.fn() });
    });
    await act(async () => {
      await result.current.choose(STALE_USE_OLD_ARCHIVE);
    });
    expect(result.current.opened).toBe(true);

    await act(async () => {
      await result.current.choose(STALE_DISABLE_ARCHIVE);
    });

    expect(request).toHaveBeenLastCalledWith(expect.objectContaining({
      stale_choice: STALE_DISABLE_ARCHIVE,
      stale_acknowledgement: expect.objectContaining({
        choice: STALE_DISABLE_ARCHIVE,
        source_snapshot_hash: 'hash-2',
      }),
    }));
  });

  it('cancels without retrying the original request', async () => {
    const request = vi.fn().mockRejectedValueOnce(staleError('hash-1'));
    const onCancel = vi.fn();
    const { result } = renderHook(() => useStaleTranslationContextRetry());

    await act(async () => {
      await result.current.submit({ payload, request, onSuccess: vi.fn(), onCancel });
    });
    await act(async () => result.current.cancel());

    expect(onCancel).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledOnce();
    expect(result.current.opened).toBe(false);
  });
});
