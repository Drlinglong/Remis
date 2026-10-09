import React from 'react';
import { Alert, Group, Select, Stack, Text, Textarea } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { confidenceBands, effectiveReviewState, parseReviewMetadata, reviewStates,
    updateReviewMetadata } from '../../utils/terminologyReview';

export default function TerminologyReviewFields({ metadata, values, locale, translations, onChange }) {
    const { t } = useTranslation();
    const term = parseReviewMetadata(metadata)?.terminology;
    if (!term) return null;
    const active = term.locale === locale;
    const patch = (value) => onChange(updateReviewMetadata(metadata, value, values));
    const state = active ? effectiveReviewState(term, values) : term.review_state;
    return (
        <Stack gap="xs">
            <Text fw={600}>{t('glossary_terminology.title')}</Text>
            <Text size="xs" c="dimmed">{term.source_id || term.concept_id}</Text>
            {!active && <Alert>{t('glossary_terminology.reference_locale', { locale: term.locale })}</Alert>}
            <Group grow>
                <Select label={t('glossary_terminology.state')} value={state} disabled={!active}
                    data={reviewStates.map((value) => ({ value, label: t(`glossary_terminology.states.${value}`) }))}
                    onChange={(value) => value && patch({ review_state: value })} allowDeselect={false} />
                <Select label={t('glossary_terminology.confidence')} value={term.confidence || 'unrated'} disabled={!active}
                    data={confidenceBands.map((value) => ({ value, label: t(`glossary_terminology.bands.${value}`) }))}
                    onChange={(value) => value && patch({ confidence: value })} allowDeselect={false} />
            </Group>
            <Text size="xs" c="dimmed">{t('glossary_terminology.confidence_note')}</Text>
            <Textarea label={t('glossary_terminology.sense')} value={term.sense || ''} disabled={!active}
                autosize minRows={2} onChange={(event) => patch({ sense: event.currentTarget.value })} />
            {!!term.context_keys?.length && <Text size="sm">{t('glossary_terminology.context')}: {term.context_keys.join(', ')}</Text>}
            {translations?.['zh-CN'] && term.locale !== 'zh-CN'
                && <Text size="sm">{t('glossary_terminology.schinese')}: {translations['zh-CN']}</Text>}
            {term.historical_reference && <Text size="sm">{t('glossary_terminology.community')}: {term.historical_reference.translation}
                <Text component="span" size="xs" c="dimmed"> ({term.historical_reference.english}; ID {term.historical_reference.source_id})</Text></Text>}
            {term.historical_reference?.source_kind === 'author_public_history'
                && <Text size="xs" c="dimmed">{t('glossary_terminology.community_author_history')}</Text>}
            {term.original_candidate && <Text size="sm">{t('glossary_terminology.original')}: {term.original_candidate}</Text>}
            {term.audit_suggestion && <Text size="sm">{t('glossary_terminology.suggestion')}: {term.audit_suggestion}</Text>}
            {term.audit_reason && <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{t('glossary_terminology.reason')}: {term.audit_reason}</Text>}
            {term.reviewer && <Text size="xs" c="dimmed">{t('glossary_terminology.reviewer')}: {term.reviewer}</Text>}
            {term.human_review && <Text size="sm">{t('glossary_terminology.human_review')}: {term.human_review.reviewer} — {term.human_review.reason}</Text>}
            {term.model_review && <Text size="sm">{t('glossary_terminology.community_review')}: {term.model_review.reviewer} — {term.model_review.reason}</Text>}
            {state === 'pending' && <Alert color="yellow">{t('glossary_terminology.pending_note')}</Alert>}
        </Stack>
    );
}
