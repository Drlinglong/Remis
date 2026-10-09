import { describe, expect, it } from 'vitest';
import { effectiveReviewState, prepareReviewMetadata, reviewBasis, updateReviewMetadata } from './terminologyReview';

const values = { source: 'Water', translation: '水量' };
const term = { locale: 'zh-TW', concept_id: 'water:1', sense: 'Terraforming', context_keys: ['source_id:1'],
    review_state: 'reviewed', confidence: 'high', audit_reason: 'Evidence', evidence_refs: [{ id: '1' }] };
const metadata = { source_lang: 'en', preserved: { custom: true }, terminology: { ...term, review_basis: reviewBasis(values, term) } };

describe('terminology review metadata', () => {
    it.each(['reviewed', 'approved'])('refreshes the alias basis on explicit %s confirmation', (reviewState) => {
        const edited = { ...values, variants: [{ lang: 'en', value: ' Water supply, H2O, ' }] };
        const imported = { ...metadata, terminology: { ...metadata.terminology,
            aliases: ['Water resource'], alias_review_basis: ['Water resource'] } };
        expect(effectiveReviewState(imported.terminology, edited)).toBe('candidate');
        const result = JSON.parse(updateReviewMetadata(JSON.stringify(imported), { review_state: reviewState }, edited));
        expect(result.terminology.alias_review_basis).toEqual(['Water supply', 'H2O']);
        expect(prepareReviewMetadata(JSON.stringify(result), edited, 'zh-TW').terminology.review_state).toBe(reviewState);
        expect(prepareReviewMetadata(JSON.stringify(result), { ...edited,
            variants: [{ lang: 'en', value: 'Changed after approval' }] }, 'zh-TW').terminology.review_state).toBe('candidate');
    });
    it('invalidates approval after source, translation or sense edits', () => {
        expect(effectiveReviewState(metadata.terminology, { ...values, translation: '新译法' })).toBe('candidate');
        expect(effectiveReviewState({ ...metadata.terminology, sense: 'Stored resource' }, values)).toBe('candidate');
        expect(effectiveReviewState(metadata.terminology, { ...values, source: 'Ice' })).toBe('candidate');
    });
    it('preserves evidence and unknown metadata when confirming a pending term', () => {
        const result = JSON.parse(updateReviewMetadata(JSON.stringify(metadata), { review_state: 'approved' }, values));
        expect(result.preserved).toEqual({ custom: true });
        expect(result.terminology.evidence_refs).toEqual([{ id: '1' }]);
        expect(result.terminology.review_state).toBe('approved');
        expect(prepareReviewMetadata(JSON.stringify(result), values, 'zh-TW')).toEqual(result);
    });
    it('saving another language preserves the target review and malformed JSON is not interpreted as a review', () => {
        expect(prepareReviewMetadata(JSON.stringify(metadata), { ...values, translation: '水资源' }, 'zh-CN')).toEqual(metadata);
        expect(updateReviewMetadata('{broken', { review_state: 'approved' }, values)).toBe('{broken');
    });
    it('JSON property order does not invalidate a review', () => {
        const basis = metadata.terminology.review_basis;
        expect(effectiveReviewState({ ...metadata.terminology, review_basis: {
            context_keys: basis.context_keys, sense: basis.sense, translation: basis.translation, source: basis.source,
        } }, values)).toBe('reviewed');
    });
});
