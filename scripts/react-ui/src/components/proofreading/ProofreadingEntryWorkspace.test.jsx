import { describe, expect, it } from 'vitest';

import {
    applyProofreadingDraftPatches,
    extractBracketTokens,
    getBracketVariableWarnings,
    isProofreadingRowChanged,
} from './proofreadingEntryState';

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

describe('proofreading entry safety helpers', () => {
    it('extracts bracket variables without treating ordinary text as a token', () => {
        expect(extractBracketTokens('The [ROOT.GetName] has [VALUE] troops.')).toEqual([
            '[ROOT.GetName]',
            '[VALUE]',
        ]);
    });

    it('reports removed, added, renamed, and count-changed variables as advisory warnings', () => {
        const warnings = getBracketVariableWarnings([{
            entry_id: 'entry-1',
            row_type: 'translation',
            key: 'demo.key:0',
            editable: true,
            baseline_value: '[ROOT] [VALUE] [VALUE]',
            final_value: '[ROOT.GetName] [VALUE]',
        }]);

        expect(warnings).toEqual([{
            entry_id: 'entry-1',
            key: 'demo.key:0',
            changes: [
                { token: '[ROOT]', before: 1, after: 0 },
                { token: '[VALUE]', before: 2, after: 1 },
                { token: '[ROOT.GetName]', before: 0, after: 1 },
            ],
        }]);
    });

    it('restores translation patches by stable key when positional entry ids changed', () => {
        const rows = [{
            entry_id: 'entry-9',
            row_type: 'translation',
            key: 'demo.key:0',
            final_value: 'Disk',
        }];
        expect(applyProofreadingDraftPatches(rows, [{
            entry_id: 'entry-1',
            row_type: 'translation',
            key: 'demo.key:0',
            final_value: 'Draft',
        }])[0].final_value).toBe('Draft');
    });
});
