import { describe, expect, it } from 'vitest';

import { isTerminalTaskStatus } from './taskStatus';

describe('taskStatus', () => {
  it.each([
    'completed',
    'success',
    'partial_failed',
    'failed',
    'cancelled',
    'canceled',
    'interrupted',
  ])('recognizes %s as terminal', (status) => {
    expect(isTerminalTaskStatus(status)).toBe(true);
  });

  it('keeps active states non-terminal', () => {
    expect(isTerminalTaskStatus('running')).toBe(false);
    expect(isTerminalTaskStatus('awaiting_approval')).toBe(false);
  });
});
