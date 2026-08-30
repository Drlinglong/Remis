import React from 'react';
import {
    Alert,
    Badge,
    Box,
    Button,
    Group,
    LoadingOverlay,
    Paper,
    ScrollArea,
    Stack,
    Text,
    ThemeIcon,
    Title,
} from '@mantine/core';
import {
    IconAlertTriangle,
    IconBulb,
    IconCheck,
    IconGavel,
    IconQuote,
} from '@tabler/icons-react';

import HighlightedTermText from './HighlightedTermText';
import JudgmentDecisionPanel from './JudgmentDecisionPanel';
import TermVariantPicker from './TermVariantPicker';
import styles from './JudgmentCourt.module.css';

const CandidateAnalysis = ({ candidate, hasDuplicates, onSelectVariant, processing, t }) => (
    <Stack gap="sm" className={styles.analysisColumn}>
        {hasDuplicates ? (
            <Alert
                icon={<IconAlertTriangle size={18} />}
                color="orange"
                variant="light"
                data-remis-surface="surface"
                className={styles.quietAlert}
                title={t('neologism_review.court.duplicate_warning_title')}
            >
                <Stack gap={4}>
                    <Text size="sm">{t('neologism_review.court.duplicate_warning_body')}</Text>
                    {(candidate.duplicate_matches || []).slice(0, 3).map((match) => (
                        <Text key={match.entry_id || match.source_term} size="xs" c="dimmed">
                            {match.source_term} - {match.glossary_name}
                        </Text>
                    ))}
                </Stack>
            </Alert>
        ) : (
            <Paper
                p="md"
                data-testid="neologism-analysis-panel"
                data-visual-priority="secondary"
                data-remis-surface="paper"
                className={styles.secondaryPanel}
            >
                <Group mb="xs">
                    <ThemeIcon color="gray" variant="light" size="sm" className={styles.paperIcon}>
                        <IconBulb size={14} />
                    </ThemeIcon>
                    <Text fw={700} size="sm">{t('neologism_review.court.ai_analysis')}</Text>
                </Group>
                <Text size="sm" lh={1.6}>{candidate.reasoning}</Text>
                {candidate.review_language && (
                    <Badge mt="sm" variant="light" color="yellow" className={styles.paperBadge}>
                        {t('neologism_review.court.review_language_badge', {
                            language: candidate.review_language,
                        })}
                    </Badge>
                )}
            </Paper>
        )}
        <TermVariantPicker
            candidate={candidate}
            disabled={processing}
            onSelect={onSelectVariant}
            t={t}
        />
    </Stack>
);

const CandidateEvidence = ({ candidate, evidenceItems, t }) => (
    <Stack className={styles.evidenceColumn}>
        <Text fw={700} c="dimmed" tt="uppercase" size="xs">
            {t('neologism_review.court.context_evidence')}
        </Text>
        <Stack gap="xs">
            {evidenceItems.map((evidence, index) => (
                <Paper
                    key={`${evidence.source_file || 'legacy'}:${index}`}
                    p="sm"
                    data-testid="neologism-evidence-card"
                    data-visual-priority="secondary"
                    data-remis-surface="paper"
                    className={styles.evidenceCard}
                >
                    <Stack gap="xs" className={styles.minWidthZero}>
                        <Group align="flex-start" gap="xs" wrap="nowrap" className={styles.minWidthZero}>
                            <IconQuote size={16} className={styles.quoteIcon} />
                            <HighlightedTermText text={evidence.snippet} term={candidate.original} />
                        </Group>
                        <Text
                            size="xs"
                            c="dimmed"
                            data-testid="neologism-evidence-source"
                            className={styles.evidenceSource}
                            style={{
                                minWidth: 0,
                                whiteSpace: 'normal',
                                overflowWrap: 'anywhere',
                                wordBreak: 'break-word',
                            }}
                        >
                            {evidence.source_file
                                ? `${evidence.source_file}${evidence.line ? `:${evidence.line}` : ''}`
                                : t('neologism_review.court.legacy_source_unlinked')}
                        </Text>
                    </Stack>
                </Paper>
            ))}
        </Stack>
    </Stack>
);

const EmptyWorkspace = ({ docketView, onOpenMining, t }) => (
    <Stack align="center" justify="center" h="100%" c="dimmed" className={styles.emptyWorkspace}>
        <IconCheck size={64} aria-hidden="true" />
        <Text size="xl">{t(docketView === 'pending'
            ? 'neologism_review.court.caught_up'
            : 'neologism_review.court.no_processed_cases')}</Text>
        {docketView === 'pending' && onOpenMining && (
            <Button
                variant="light"
                data-remis-action="secondary"
                className={styles.secondaryAction}
                onClick={onOpenMining}
            >
                {t('neologism_review.tab_mining')}
            </Button>
        )}
    </Stack>
);

const JudgmentCaseWorkspace = ({
    batchProcessing,
    candidate,
    docketView,
    editSuggestion,
    evidenceItems,
    hasCandidates,
    loading,
    onApprove,
    onOpenMining,
    onReject,
    onRestore,
    onSelectVariant,
    onSuggestionChange,
    processing,
    projectSelected,
    resolution,
    setResolution,
    t,
}) => {
    if (!candidate) {
        if (!projectSelected) {
            return (
                <Stack align="center" justify="center" h="100%" c="dimmed">
                    <IconGavel size={64} className={styles.emptyIcon} />
                    <Text size="xl">{t('neologism_review.court.select_case')}</Text>
                </Stack>
            );
        }
        if (hasCandidates || loading) {
            return (
                <Stack align="center" justify="center" h="100%" c="dimmed">
                    <IconGavel size={64} className={styles.emptyIcon} />
                    <Text size="xl">{t('neologism_review.court.select_case')}</Text>
                </Stack>
            );
        }
        return <EmptyWorkspace docketView={docketView} onOpenMining={onOpenMining} t={t} />;
    }

    const sourceFile = candidate.source_file || candidate.source_files?.[0] || '';
    const sourceName = sourceFile.split(/[\\/]/).pop() || t('neologism_review.court.unknown_source');
    const hasDuplicates = Boolean(candidate.duplicate_matches?.length);

    return (
        <Stack
            key={candidate.id}
            h="100%"
            gap="sm"
            aria-busy={processing || batchProcessing}
            data-testid="neologism-review-workspace"
            className={`${styles.caseWorkspace} ${styles.caseWorkspaceMotion}`}
        >
            <LoadingOverlay visible={processing} />
            <ScrollArea
                type="always"
                scrollbars="y"
                scrollbarSize={8}
                className={styles.caseScroll}
            >
                <Stack gap="md" className={styles.caseScrollContent}>
                    <Paper
                        p="md"
                        data-testid="neologism-candidate-anchor"
                        data-visual-priority="primary"
                        data-remis-surface="surface"
                        aria-live="polite"
                        aria-atomic="true"
                        className={styles.candidateAnchor}
                    >
                        <Group align="flex-start" justify="space-between" wrap="nowrap">
                            <Box className={styles.minWidthZero}>
                                <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>
                                    {t('neologism_review.court.candidate_term')}
                                </Text>
                                <Title order={2} className={styles.caseTitle}>{candidate.original}</Title>
                            </Box>
                            <Badge
                                size="md"
                                variant="outline"
                                color="gray"
                                title={sourceFile || sourceName}
                                className={`${styles.surfaceBadge} ${styles.sourceBadge}`}
                            >
                                {sourceName}
                            </Badge>
                        </Group>
                    </Paper>
                    <div className={styles.caseBodyGrid}>
                        <CandidateAnalysis
                            candidate={candidate}
                            hasDuplicates={hasDuplicates}
                            onSelectVariant={onSelectVariant}
                            processing={processing}
                            t={t}
                        />
                        <CandidateEvidence candidate={candidate} evidenceItems={evidenceItems} t={t} />
                    </div>
                </Stack>
            </ScrollArea>
            <JudgmentDecisionPanel
                batchProcessing={batchProcessing}
                candidate={candidate}
                docketView={docketView}
                editSuggestion={editSuggestion}
                onApprove={onApprove}
                onReject={onReject}
                onResetSuggestion={() => onSuggestionChange(candidate.suggestion || '')}
                onRestore={onRestore}
                onSuggestionChange={onSuggestionChange}
                processing={processing}
                resolution={resolution}
                setResolution={setResolution}
                t={t}
            />
        </Stack>
    );
};

export default JudgmentCaseWorkspace;
