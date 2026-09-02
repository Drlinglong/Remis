import React from 'react';
import { Badge, Box, Button, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { IconChevronDown, IconChevronRight, IconCheck } from '@tabler/icons-react';

import { JUDGMENT_TIERS } from './useJudgmentCourtPresentation';
import styles from './JudgmentCourt.module.css';

const CandidateCard = ({ candidate, onOpenCandidate, t }) => (
    <Paper
        component="button"
        type="button"
        p="md"
        data-remis-surface="paper"
        className={styles.candidateCard}
        onClick={() => onOpenCandidate(candidate.id)}
        aria-label={t('neologism_review.court.open_candidate_detail', { term: candidate.original })}
    >
        <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Title order={3} size="h5" lineClamp={2} className={styles.candidateName}>
                {candidate.original}
            </Title>
            {(candidate.duplicate_matches || []).length > 0 && (
                <Badge color="orange" variant="light" size="xs">
                    {t('neologism_review.court.duplicate_badge')}
                </Badge>
            )}
        </Group>
        <Text size="sm" mt="xs" lineClamp={3}>
            {candidate.suggestion || t('neologism_review.court.no_suggestion')}
        </Text>
    </Paper>
);

const JudgmentCourtCardView = ({
    collapsedTiers,
    groupedCandidates,
    onOpenCandidate,
    onToggleTier,
    t,
}) => {
    const visibleTotal = JUDGMENT_TIERS.reduce(
        (total, tier) => total + groupedCandidates[tier].length,
        0,
    );

    return (
        <Box className={styles.cardViewScroll} data-testid="judgment-court-card-view">
            {visibleTotal === 0 ? (
                <Stack align="center" justify="center" h="100%" c="dimmed">
                    <IconCheck size={48} className={styles.emptyIcon} />
                    <Text>{t('neologism_review.court.no_filter_matches')}</Text>
                </Stack>
            ) : (
                <Stack gap="md">
                    {JUDGMENT_TIERS.map((tier) => {
                        const candidates = groupedCandidates[tier];
                        if (candidates.length === 0) return null;
                        const collapsed = collapsedTiers.has(tier);
                        const regionId = `judgment-tier-${tier}`;
                        const Chevron = collapsed ? IconChevronRight : IconChevronDown;
                        return (
                            <section key={tier} aria-labelledby={`${regionId}-title`}>
                                <Button
                                    id={`${regionId}-title`}
                                    variant="subtle"
                                    color="gray"
                                    px="xs"
                                    mb="xs"
                                    onClick={() => onToggleTier(tier)}
                                    aria-expanded={!collapsed}
                                    aria-controls={regionId}
                                    leftSection={<Chevron size={16} aria-hidden="true" />}
                                >
                                    {t(`neologism_review.court.tier_${tier.toLowerCase()}`, {
                                        count: candidates.length,
                                    })}
                                </Button>
                                <Box
                                    id={regionId}
                                    hidden={collapsed}
                                    className={styles.candidateCardGrid}
                                >
                                    {candidates.map((candidate) => (
                                        <CandidateCard
                                            key={candidate.id}
                                            candidate={candidate}
                                            onOpenCandidate={onOpenCandidate}
                                            t={t}
                                        />
                                    ))}
                                </Box>
                            </section>
                        );
                    })}
                </Stack>
            )}
        </Box>
    );
};

export default JudgmentCourtCardView;
