import { describe, expect, it } from 'vitest';

import { isProofreadingRowChanged } from './proofreadingEntryState';

describe('isProofreadingRowChanged', () => {
    it('does not treat a pre-existing difference from the AI draft as a current edit', () => {
        expect(isProofreadingRowChanged({
            editable: true,
            ai_value: 'AI draft',
            baseline_value: 'Existing disk translation',
            final_value: 'Existing disk translation',
        })).toBe(false);
    });

    it('detects edits made after the row was loaded', () => {
        expect(isProofreadingRowChanged({
            editable: true,
            baseline_value: 'Existing disk translation',
            final_value: 'User edit',
        })).toBe(true);
    });
});
