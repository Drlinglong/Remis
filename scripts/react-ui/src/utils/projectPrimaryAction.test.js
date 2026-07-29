import { describe, expect, it } from 'vitest';

import { getProjectPrimaryAction } from './projectPrimaryAction';

const project = (overrides = {}) => ({
  status: 'active',
  overview: { translated: 0, toBeProofread: 0 },
  validation: { issues_count: 0 },
  ...overrides,
});

describe('getProjectPrimaryAction', () => {
  it('prioritizes format blockers before translation or deployment', () => {
    expect(getProjectPrimaryAction(project({ validation: { issues_count: 3 } }))).toBe('fix_format');
  });

  it('progressively reveals proofreading and deployment actions', () => {
    expect(getProjectPrimaryAction(project({ overview: { translated: 80, toBeProofread: 20 } }))).toBe('proofread');
    expect(getProjectPrimaryAction(project({ overview: { translated: 100, toBeProofread: 0 } }))).toBe('deploy');
  });
});
