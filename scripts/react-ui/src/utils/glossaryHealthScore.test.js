import { describe, expect, it } from 'vitest';

import { getGlossaryHealthPenaltyBreakdown } from './glossaryHealthScore';

describe('getGlossaryHealthPenaltyBreakdown', () => {
  it('matches the deterministic service weights and applies the cap per rule', () => {
    expect(getGlossaryHealthPenaltyBreakdown([
      { code: 'empty_source', severity: 'error', count: 12 },
      { code: 'placeholder_mismatch', severity: 'error', count: 2 },
      { code: 'missing_translation', severity: 'warning', count: 4 },
      { code: 'duplicate_term', severity: 'info', count: 3 },
      { code: 'future_info', severity: 'info', count: 9 },
    ])).toEqual({
      error: { findings: 12, penalty: 96 },
      warning: { findings: 4, penalty: 12 },
      info: { findings: 12, penalty: 12 },
      totalPenalty: 120,
    });
  });
});
