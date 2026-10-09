import React from 'react';
import { Badge, Group } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { effectiveReviewState } from '../../utils/terminologyReview';

export default function TerminologyReviewBadge({ entry }) {
    const { t } = useTranslation();
    const term = entry.metadata?.terminology;
    if (!term) return null;
    const state = effectiveReviewState(term, { source: entry.source, translation: entry.translations?.[term.locale] });
    return <Group gap="xs">
        <Badge color={state === 'pending' ? 'yellow' : state === 'approved' ? 'green' : 'gray'}>
            {t(`glossary_terminology.states.${state}`)}
        </Badge>
        <Badge variant="outline">{t(`glossary_terminology.bands.${term.confidence || 'unrated'}`)}</Badge>
    </Group>;
}
