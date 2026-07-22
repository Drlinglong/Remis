import { describe, expect, it } from 'vitest';

import { formatTaskDuration, taskDurationMs } from './taskTime';

describe('task time helpers', () => {
  it('keeps active tasks ticking against the supplied clock', () => {
    const duration = taskDurationMs(
      { status: 'running', started_at: '2026-07-22T00:00:00Z' },
      new Date('2026-07-22T01:02:03Z').getTime(),
    );
    expect(formatTaskDuration(duration)).toBe('01:02:03');
  });

  it('freezes terminal tasks at finished_at', () => {
    const duration = taskDurationMs({
      status: 'failed',
      started_at: '2026-07-22T00:00:00Z',
      finished_at: '2026-07-22T00:00:08Z',
    });
    expect(formatTaskDuration(duration)).toBe('00:00:08');
  });
});
