import { describe, expect, it, vi } from 'vitest';

import { pollAgentWorkshopRun } from './agentWorkshopRunMonitor';

describe('pollAgentWorkshopRun', () => {
  it('keeps polling until a run reaches a terminal status', async () => {
    const getStatus = vi.fn()
      .mockResolvedValueOnce({ status: 'running', progress: { percent: 25 } })
      .mockResolvedValueOnce({ status: 'completed', progress: { percent: 100 } });
    const onTask = vi.fn();

    await expect(pollAgentWorkshopRun({
      taskId: 'task-1',
      getStatus,
      onTask,
      waitForNext: vi.fn().mockResolvedValue(undefined),
    })).resolves.toMatchObject({ status: 'completed' });

    expect(getStatus).toHaveBeenCalledTimes(2);
    expect(onTask).toHaveBeenNthCalledWith(1, expect.objectContaining({ status: 'running' }));
    expect(onTask).toHaveBeenNthCalledWith(2, expect.objectContaining({ status: 'completed' }));
  });

  it('stops without another request when the restored page is cancelled', async () => {
    const getStatus = vi.fn();

    await expect(pollAgentWorkshopRun({
      taskId: 'task-2',
      getStatus,
      onTask: vi.fn(),
      isCancelled: () => true,
      waitForNext: vi.fn().mockResolvedValue(undefined),
    })).resolves.toBeNull();

    expect(getStatus).not.toHaveBeenCalled();
  });

  it('rejects malformed task payloads instead of silently abandoning recovery', async () => {
    await expect(pollAgentWorkshopRun({
      taskId: 'task-3',
      getStatus: vi.fn().mockResolvedValue({ progress: { percent: 10 } }),
      onTask: vi.fn(),
      waitForNext: vi.fn().mockResolvedValue(undefined),
    })).rejects.toThrow('missing status');
  });

  it('treats partial failure as a terminal result that needs review', async () => {
    const onTask = vi.fn();

    await expect(pollAgentWorkshopRun({
      taskId: 'task-partial',
      getStatus: vi.fn().mockResolvedValue({
        status: 'partial_failed',
        progress: { percent: 100 },
      }),
      onTask,
      waitForNext: vi.fn().mockResolvedValue(undefined),
    })).resolves.toMatchObject({ status: 'partial_failed' });

    expect(onTask).toHaveBeenCalledTimes(1);
  });
});
