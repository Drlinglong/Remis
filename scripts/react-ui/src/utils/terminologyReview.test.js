import { describe, expect, it } from 'vitest';
import { effectiveReviewState, prepareReviewMetadata, reviewBasis, updateReviewMetadata } from './terminologyReview';

const values = { source: 'Water', translation: '水量' };
const term = { locale: 'zh-TW', concept_id: 'water:1', sense: 'Terraforming', context_keys: ['source_id:1'],
    review_state: 'reviewed', confidence: 'high', audit_reason: 'Evidence', evidence_refs: [{ id: '1' }] };
const metadata = { source_lang: 'en', preserved: { custom: true }, terminology: { ...term, review_basis: reviewBasis(values, term) } };

describe('terminology review metadata', () => {
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
