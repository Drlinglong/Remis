import React from 'react';
import { Button, Group, SegmentedControl, TextInput } from '@mantine/core';
import {
    IconCheck,
    IconLayoutGrid,
    IconListDetails,
    IconSearch,
    IconTrash,
} from '@tabler/icons-react';

import styles from './JudgmentCourt.module.css';

const iconLabel = (Icon, label) => (
    <Group gap={6} wrap="nowrap">
        <Icon size={14} aria-hidden="true" />
        <span>{label}</span>
    </Group>
);

const JudgmentCourtViewToolbar = ({
    candidateCount,
    disabled,
    docketView,
    duplicateCount,
    onApproveAll,
    onDocketViewChange,
    onRejectDuplicates,
    onSearchQueryChange,
    onTierFilterChange,
    onViewModeChange,
    searchQuery,
    t,
    tierFilter,
    viewMode,
}) => (
    <div
        className={styles.viewToolbarSlot}
        data-testid="judgment-court-view-toolbar"
        data-remis-surface="surface"
    >
        <Group gap="xs" wrap="wrap">
            <SegmentedControl
                size="xs"
                value={viewMode}
                onChange={onViewModeChange}
                aria-label={t('neologism_review.court.view_mode')}
                data={[
                    { value: 'detail', label: iconLabel(IconListDetails, t('neologism_review.court.detail_view')) },
                    { value: 'cards', label: iconLabel(IconLayoutGrid, t('neologism_review.court.card_view')) },
                ]}
            />
            <SegmentedControl
                size="xs"
                value={docketView}
                onChange={onDocketViewChange}
                aria-label={t('neologism_review.court.docket_view')}
                data={[
                    { value: 'pending', label: t('neologism_review.court.pending_docket') },
                    { value: 'processed', label: t('neologism_review.court.processed_docket') },
                ]}
            />
            <SegmentedControl
                size="xs"
                value={tierFilter}
                onChange={onTierFilterChange}
                aria-label={t('neologism_review.court.tier_filter')}
                data={[
                    { value: 'all', label: t('neologism_review.court.tier_all') },
                    { value: 'A', label: 'A' },
                    { value: 'B', label: 'B' },
                    { value: 'C', label: 'C' },
                ]}
            />
            <TextInput
                size="xs"
                value={searchQuery}
                onChange={(event) => onSearchQueryChange(event.currentTarget.value)}
                placeholder={t('neologism_review.court.search_placeholder')}
                aria-label={t('neologism_review.court.search_label')}
                leftSection={<IconSearch size={14} aria-hidden="true" />}
                classNames={{ input: styles.semanticField }}
                className={styles.viewSearch}
            />
            {docketView === 'pending' && (
                <Group gap="xs" ml="auto" wrap="wrap">
                    <Button
                        size="compact-xs"
                        variant="light"
                        color="red"
                        leftSection={<IconTrash size={14} />}
                        onClick={onRejectDuplicates}
                        disabled={disabled || duplicateCount === 0}
                    >
                        {t('neologism_review.court.reject_all_duplicates', { count: duplicateCount })}
                    </Button>
                    <Button
                        size="compact-xs"
                        color="teal"
                        leftSection={<IconCheck size={14} />}
                        onClick={onApproveAll}
                        disabled={disabled || candidateCount === 0}
                        aria-label={t('neologism_review.court.save_all_action', {
                            count: candidateCount,
                        })}
                    >
                        {t('neologism_review.court.approve_all', { count: candidateCount })}
                    </Button>
                </Group>
            )}
        </Group>
    </div>
);

export default JudgmentCourtViewToolbar;
