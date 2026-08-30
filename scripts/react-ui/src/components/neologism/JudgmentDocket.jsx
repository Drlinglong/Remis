import React, { useEffect, useRef } from 'react';
import {
    Badge,
    Box,
    Button,
    Checkbox,
    Group,
    Paper,
    SegmentedControl,
    Stack,
    Text,
    Title,
} from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';

import styles from './JudgmentCourt.module.css';

const CandidateBadges = ({ candidate, docketView, t }) => (
    <Group gap={4} wrap="wrap">
        {candidate.tier && (
            <Badge
                color={candidate.tier === 'A' ? 'green' : (candidate.tier === 'B' ? 'blue' : 'gray')}
                variant="light"
                size="xs"
                className={styles.surfaceBadge}
            >
                {candidate.tier}
            </Badge>
        )}
        {(candidate.duplicate_matches || []).length > 0 && (
            <Badge color="orange" variant="light" size="xs" className={styles.surfaceBadge}>
                {t('neologism_review.court.duplicate_badge')}
            </Badge>
        )}
        {docketView === 'processed' && (
            <Badge color="blue" variant="light" size="xs" className={styles.surfaceBadge}>
                {t(`neologism_review.court.status_${candidate.status}`)}
            </Badge>
        )}
    </Group>
);

const JudgmentDocket = ({
    batchProcessing,
    batchSelectedIds,
    candidates,
    docketView,
    focusRequest,
    loading,
    onBatchConfirm,
    onDocketViewChange,
    onSelectCandidate,
    onToggleAll,
    onToggleCandidate,
    processing,
    selectedId,
    t,
}) => {
    const candidateButtonRefs = useRef(new Map());
    const docketRef = useRef(null);

    useEffect(() => {
        if (!focusRequest) return;
        const selectedButton = candidateButtonRefs.current.get(selectedId);
        (selectedButton || docketRef.current)?.focus();
    }, [focusRequest, selectedId]);

    const handleCandidateKeyDown = (event, candidateIndex) => {
        const navigationKeys = ['ArrowDown', 'ArrowUp', 'Home', 'End'];
        if (!navigationKeys.includes(event.key)) return;
        event.preventDefault();

        let nextIndex = candidateIndex;
        if (event.key === 'ArrowDown') nextIndex = Math.min(candidateIndex + 1, candidates.length - 1);
        if (event.key === 'ArrowUp') nextIndex = Math.max(candidateIndex - 1, 0);
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = candidates.length - 1;

        const nextCandidate = candidates[nextIndex];
        if (!nextCandidate) return;
        onSelectCandidate(nextCandidate.id);
        candidateButtonRefs.current.get(nextCandidate.id)?.focus();
    };

    return (
        <aside
            ref={docketRef}
            tabIndex={-1}
            aria-labelledby="neologism-docket-title"
            data-testid="neologism-docket-panel"
            data-remis-surface="surface"
            className={styles.docketPanel}
        >
        <Stack p="sm" gap="xs" h="100%" className={styles.docketStack}>
            <Group justify="space-between">
                <Title id="neologism-docket-title" order={4} c="dimmed">
                    {t('neologism_review.court.docket')}
                </Title>
                <Badge variant="dot" size="lg" className={styles.surfaceBadge}>
                    {candidates.length}
                </Badge>
            </Group>
            <SegmentedControl
                fullWidth
                size="xs"
                value={docketView}
                onChange={onDocketViewChange}
                data={[
                    { value: 'pending', label: t('neologism_review.court.pending_docket') },
                    { value: 'processed', label: t('neologism_review.court.processed_docket') },
                ]}
            />
            {candidates.length > 0 && (
                <Stack gap="xs" className={styles.batchToolbar}>
                    <Checkbox
                        size="xs"
                        label={t('neologism_review.court.select_all')}
                        checked={batchSelectedIds.length === candidates.length}
                        indeterminate={batchSelectedIds.length > 0 && batchSelectedIds.length < candidates.length}
                        onChange={onToggleAll}
                        disabled={processing || batchProcessing}
                    />
                    {batchSelectedIds.length > 0 && (
                        <Group grow gap="xs" className={styles.batchActions}>
                            {docketView === 'pending' ? (
                                <>
                                    <Button
                                        size="compact-xs"
                                        variant="light"
                                        color="green"
                                        onClick={() => onBatchConfirm('approve')}
                                        disabled={processing || batchProcessing}
                                    >
                                        {t('neologism_review.court.batch_approve', { count: batchSelectedIds.length })}
                                    </Button>
                                    <Button
                                        size="compact-xs"
                                        variant="light"
                                        color="red"
                                        onClick={() => onBatchConfirm('reject')}
                                        disabled={processing || batchProcessing}
                                    >
                                        {t('neologism_review.court.batch_reject', { count: batchSelectedIds.length })}
                                    </Button>
                                </>
                            ) : (
                                <Button
                                    size="compact-xs"
                                    variant="light"
                                    color="blue"
                                    onClick={() => onBatchConfirm('restore')}
                                    disabled={processing || batchProcessing}
                                >
                                    {t('neologism_review.court.batch_restore', { count: batchSelectedIds.length })}
                                </Button>
                            )}
                        </Group>
                    )}
                </Stack>
            )}
            <Box
                data-testid="neologism-docket-scroll"
                className={styles.docketScroll}
                style={{
                    flex: '1 1 0',
                    minHeight: 0,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                }}
            >
                <Stack gap="xs">
                    {candidates.map((candidate, candidateIndex) => (
                        <Group key={candidate.id} gap="xs" wrap="nowrap" align="center">
                            <Checkbox
                                size="xs"
                                checked={batchSelectedIds.includes(candidate.id)}
                                onChange={() => onToggleCandidate(candidate.id)}
                                aria-label={t('neologism_review.court.select_candidate', {
                                    term: candidate.original,
                                })}
                                disabled={processing || batchProcessing}
                            />
                            <Paper
                                ref={(node) => {
                                    if (node) candidateButtonRefs.current.set(candidate.id, node);
                                    else candidateButtonRefs.current.delete(candidate.id);
                                }}
                                component="button"
                                type="button"
                                p="sm"
                                onClick={() => onSelectCandidate(candidate.id)}
                                onKeyDown={(event) => handleCandidateKeyDown(event, candidateIndex)}
                                aria-pressed={selectedId === candidate.id}
                                aria-controls="neologism-review-panel"
                                tabIndex={selectedId === candidate.id ? 0 : -1}
                                data-remis-surface="surface"
                                className={styles.candidateButton}
                            >
                                <Group justify="space-between" align="flex-start" wrap="nowrap">
                                    <Text size="sm" fw={600} lineClamp={1} className={styles.candidateName}>
                                        {candidate.original}
                                    </Text>
                                    <CandidateBadges candidate={candidate} docketView={docketView} t={t} />
                                </Group>
                                <Text size="xs" c="dimmed" truncate>{candidate.suggestion}</Text>
                            </Paper>
                        </Group>
                    ))}
                    {candidates.length === 0 && !loading && (
                        <Stack align="center" mt="xl" c="dimmed">
                            <IconCheck size={32} />
                            <Text>{t(docketView === 'pending'
                                ? 'neologism_review.court.caught_up'
                                : 'neologism_review.court.no_processed_cases')}</Text>
                        </Stack>
                    )}
                </Stack>
            </Box>
        </Stack>
        </aside>
    );
};

export default JudgmentDocket;
