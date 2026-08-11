import React from 'react';
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
    loading,
    onBatchConfirm,
    onDocketViewChange,
    onSelectCandidate,
    onToggleAll,
    onToggleCandidate,
    processing,
    selectedId,
    t,
}) => (
    <aside
        data-testid="neologism-docket-panel"
        data-remis-surface="surface"
        className={styles.docketPanel}
    >
        <Stack p="sm" gap="xs" h="100%" className={styles.docketStack}>
            <Group justify="space-between">
                <Title order={4} c="dimmed">{t('neologism_review.court.docket')}</Title>
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
                        <Group grow gap="xs">
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
                    {candidates.map((candidate) => (
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
                                component="button"
                                type="button"
                                p="sm"
                                onClick={() => onSelectCandidate(candidate.id)}
                                aria-pressed={selectedId === candidate.id}
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

export default JudgmentDocket;
