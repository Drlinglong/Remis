import React from 'react';
import {
    ActionIcon,
    Box,
    Button,
    Group,
    Paper,
    Select,
    Text,
    TextInput,
} from '@mantine/core';
import { IconGavel, IconRestore, IconSparkles, IconX } from '@tabler/icons-react';

import styles from './JudgmentCourt.module.css';

const JudgmentDecisionPanel = ({
    batchProcessing,
    candidate,
    docketView,
    editSuggestion,
    onApprove,
    onReject,
    onResetSuggestion,
    onRestore,
    onSuggestionChange,
    processing,
    resolution,
    setResolution,
    t,
}) => {
    if (docketView !== 'pending') {
        return (
            <Paper
                p="sm"
                withBorder
                data-testid="neologism-decision-panel"
                data-remis-surface="surface"
                className={styles.decisionPanel}
            >
                <Group justify="space-between" align="center" wrap="wrap">
                    <Box className={styles.minWidthZero}>
                        <Text fw={700}>{t(`neologism_review.court.status_${candidate.status}`)}</Text>
                        <Text size="sm" c="dimmed">
                            {t(['approved', 'new_meaning'].includes(candidate.status)
                                ? 'neologism_review.court.restore_preserves_glossary_note'
                                : 'neologism_review.court.restore_note')}
                        </Text>
                    </Box>
                    <Button
                        color="blue"
                        variant="light"
                        data-remis-action="secondary"
                        className={styles.secondaryAction}
                        leftSection={<IconRestore size={18} />}
                        onClick={onRestore}
                        disabled={batchProcessing}
                    >
                        {t('neologism_review.court.restore_candidate')}
                    </Button>
                </Group>
            </Paper>
        );
    }

    return (
        <Paper
            p="sm"
            data-testid="neologism-decision-panel"
            data-visual-priority="action"
            data-remis-surface="surface"
            className={styles.decisionPanel}
        >
            {(candidate.duplicate_matches || []).length > 0 && (
                <Select
                    mb="sm"
                    label={t('neologism_review.court.duplicate_resolution')}
                    data={[
                        { value: 'duplicate', label: t('neologism_review.court.resolution_duplicate') },
                        { value: 'approve_project', label: t('neologism_review.court.resolution_override') },
                        { value: 'new_meaning', label: t('neologism_review.court.resolution_new_meaning') },
                    ]}
                    value={resolution}
                    onChange={setResolution}
                    classNames={{
                        wrapper: styles.semanticFieldWrapper,
                        label: styles.semanticFieldLabel,
                        input: styles.semanticField,
                    }}
                />
            )}
            <TextInput
                label={t('neologism_review.court.final_translation')}
                description={t('neologism_review.court.final_translation_desc')}
                size="md"
                value={editSuggestion}
                onChange={(event) => onSuggestionChange(event.currentTarget.value)}
                classNames={{
                    wrapper: styles.semanticFieldWrapper,
                    label: styles.semanticFieldLabel,
                    description: styles.semanticFieldDescription,
                    input: styles.semanticField,
                }}
                rightSection={(
                    <ActionIcon
                        variant="subtle"
                        className={styles.resetSuggestion}
                        onClick={onResetSuggestion}
                        aria-label={t('neologism_review.court.reset_suggestion', 'Reset suggestion')}
                    >
                        <IconSparkles size={18} />
                    </ActionIcon>
                )}
            />
            <Group mt="sm" justify="flex-end" wrap="wrap">
                <Button
                    size="sm"
                    variant="subtle"
                    color="red"
                    data-testid="neologism-reject-action"
                    data-remis-action="danger-secondary"
                    className={styles.dangerSecondaryAction}
                    leftSection={<IconX />}
                    onClick={onReject}
                    disabled={batchProcessing}
                >
                    {t('neologism_review.court.ignore')}
                </Button>
                <Button
                    size="md"
                    variant="filled"
                    color="teal"
                    data-testid="neologism-approve-action"
                    data-remis-action="primary"
                    className={styles.primaryAction}
                    leftSection={<IconGavel />}
                    onClick={onApprove}
                    loading={processing}
                    disabled={batchProcessing || (resolution !== 'duplicate' && !editSuggestion.trim())}
                >
                    {t('neologism_review.court.approve')}
                </Button>
            </Group>
        </Paper>
    );
};

export default JudgmentDecisionPanel;
