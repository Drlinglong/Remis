import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import { useHomeDashboardData } from './useHomeDashboardData';

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn() },
}));

describe('useHomeDashboardData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('owns the dashboard request lifecycle and exposes a ready model', async () => {
    api.get.mockResolvedValueOnce({
      data: { stats: { total_projects: 4 }, charts: {}, recent_activity: [] },
    });

    const { result } = renderHook(() => useHomeDashboardData({ language: 'en' }));

    expect(result.current.phase).toBe('loading');
    await waitFor(() => expect(result.current.phase).toBe('ready'));
    expect(api.get).toHaveBeenCalledWith('/api/system/stats');
    expect(result.current.data.stats.total_projects).toBe(4);
  });

  it('keeps the failure explicit and supports a focused retry', async () => {
    api.get.mockRejectedValueOnce(new Error('dashboard offline'));
    const { result } = renderHook(() => useHomeDashboardData({ language: 'en' }));

    await waitFor(() => expect(result.current.phase).toBe('error'));
    expect(result.current.error).toHaveProperty('message', 'dashboard offline');
    expect(result.current.data.stats.total_projects).toBeNull();

    api.get.mockResolvedValueOnce({ data: { stats: { total_projects: 1 } } });
    await act(async () => result.current.refresh());
    await waitFor(() => expect(result.current.phase).toBe('ready'));
    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
