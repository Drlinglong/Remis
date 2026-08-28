import { describe, expect, it } from 'vitest';

import { normalizeArrayPayload, normalizeRecordArrayPayload } from './payload';

describe('collection payload normalization', () => {
  it('unwraps bare arrays and nested common wrappers', () => {
    expect(normalizeRecordArrayPayload([{ id: 'bare' }], ['archives'])).toEqual([{ id: 'bare' }]);
    expect(normalizeRecordArrayPayload({ data: { archives: [{ id: 'wrapped' }] } }, ['archives'])).toEqual([
      { id: 'wrapped' },
    ]);
    expect(normalizeArrayPayload({ data: { archives: [{ id: 'nested' }] } }, ['archives'])).toEqual([]);
  });

  it('returns only object records for null or malformed collections', () => {
    expect(normalizeRecordArrayPayload({ data: { history: [null, 'invalid', {}, { history_id: 'h1' }] } }, ['history'])).toEqual([
      { history_id: 'h1' },
    ]);
    expect(normalizeRecordArrayPayload(null, ['history'])).toEqual([]);
  });
});
