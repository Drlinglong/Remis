import { describe, expect, it, vi } from 'vitest';

import { pollGlossaryTask } from './glossaryTaskMonitor';

describe('pollGlossaryTask', () => {
  it('polls until a terminal task is returned', async () => {
    const getTask = vi.fn()
      .mockResolvedValueOnce({ status: 'running' })
      .mockResolvedValueOnce({ status: 'completed', result: { score: 90 } });
    const onTask = vi.fn();

    const task = await pollGlossaryTask({
      taskId: 'health-task',
      getTask,
      onTask,
      waitForNext: () => Promise.resolve(),
    });

    expect(task.status).toBe('completed');
    expect(getTask).toHaveBeenCalledTimes(2);
    expect(onTask).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'completed' }));
  });

  it('stops without publishing another task after cancellation', async () => {
    let cancelled = false;
    const getTask = vi.fn().mockResolvedValue({ status: 'running' });
    const onTask = vi.fn();

    const task = await pollGlossaryTask({
      taskId: 'health-task',
      getTask,
      onTask,
      isCancelled: () => cancelled,
      waitForNext: () => {
        cancelled = true;
        return Promise.resolve();
      },
    });

    expect(task).toBeNull();
    expect(getTask).toHaveBeenCalledTimes(1);
    expect(onTask).toHaveBeenCalledTimes(1);
  });

  it('rejects malformed task payloads instead of polling forever', async () => {
    await expect(pollGlossaryTask({
      taskId: 'health-task',
      getTask: vi.fn().mockResolvedValue({}),
      onTask: vi.fn(),
    })).rejects.toThrow('missing status');
  });
});
