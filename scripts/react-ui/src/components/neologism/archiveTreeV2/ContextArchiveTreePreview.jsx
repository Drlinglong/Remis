import React, { useMemo } from 'react';
import {
    Badge,
    Group,
    Paper,
    Select,
    Stack,
    Text,
    Title,
} from '@mantine/core';

import {
    buildNarrativeUnitPreview,
    getTreeUnitOptions,
    groupReferenceAssetsByTier,
} from './contextArchiveTreeModel';
import styles from './ContextArchiveTree.module.css';

const label = (t, key, fallback, options = {}) => t(key, { ...options, defaultValue: fallback });

const SelectedFragmentPanel = ({ fragment, t }) => {
    if (!fragment) {
        return (
            <div className={styles.selectionEmpty} data-testid="context-tree-selected-fragment-empty">
                {label(t, 'mod_archive.tree.select_fragment', 'Select a fragment in the map to inspect its evidence and delivery route.')}
            </div>
        );
    }
    return (
        <Paper className={styles.selectedFragment} p="sm" withBorder data-remis-surface="paper" data-testid="context-tree-selected-fragment">
            <Text className={styles.summaryEyebrow}>{label(t, 'mod_archive.tree.selected_fragment_eyebrow', 'SELECTED FRAGMENT')}</Text>
            <Text fw={700} className={styles.selectedFragmentTitle}>{fragment.label}</Text>
            <Text size="sm" className={styles.selectedFragmentSummary}>
                {label(t, 'mod_archive.tree.fragment_summary', 'Summary')} · {fragment.summary}
            </Text>
            <Group className={styles.selectedFragmentMeta} gap="xs" wrap="wrap">
                <Badge size="xs" variant="outline">{fragment.route || '—'}</Badge>
                <Badge size="xs" variant="light">{fragment.tier || '—'}</Badge>
                <Text size="xs" className={styles.muted}>
                    {label(t, 'mod_archive.tree.units', 'Units')}: {fragment.unitIds?.length || 0}
                    {' · '}
                    {label(t, 'mod_archive.tree.evidence', 'Evidence')}: {fragment.evidenceIds?.length || 0}
                </Text>
            </Group>
        </Paper>
    );
};

const ReferenceAssetPanel = ({ tree, t }) => {
    const groups = useMemo(
        () => groupReferenceAssetsByTier(tree.referenceAssets),
        [tree.referenceAssets],
    );
    return (
        <Paper className={styles.referencePanel} p="md" withBorder data-remis-surface="paper" data-testid="context-tree-reference-assets">
            <Group className={styles.referenceHeader} justify="space-between">
                <div>
                    <Title order={4}>{label(t, 'mod_archive.tree.reference_assets', 'Related reference assets')}</Title>
                    <Text className={styles.muted} size="sm">
                        {label(t, 'mod_archive.tree.reference_assets_desc', 'Reference assets do not receive event-chain context.')}
                    </Text>
                </div>
                <Badge variant="outline">{tree.referenceAssets.length}</Badge>
            </Group>
            {groups.length === 0 ? (
                <Text className={styles.muted} size="sm" mt="sm">
                    {label(t, 'mod_archive.tree.no_reference_assets', 'No reference assets are linked.')}
                </Text>
            ) : groups.map((group) => (
                <details
                    className={styles.referenceDetails}
                    key={group.tier}
                    open={group.openByDefault}
                    data-testid={`context-tree-reference-tier-${group.tier}`}
                >
                    <summary className={styles.referenceSummary}>
                        <span>{label(t, `mod_archive.tree.tier_${group.tier.toLowerCase()}`, `${group.tier} reference assets`)}</span>
                        <Badge size="sm" variant="light">{group.assets.length}</Badge>
                    </summary>
                    <div className={styles.referenceList}>
                        {group.assets.map((asset) => (
                            <Paper className={styles.referenceAsset} key={asset.id} withBorder data-remis-surface="paper">
                                <Group justify="space-between" align="flex-start" gap="xs">
                                    <Text fw={700} className={styles.fragmentLabel}>{asset.label}</Text>
                                    <Badge size="xs" variant="outline">{asset.tier}</Badge>
                                </Group>
                                {asset.summary && <Text size="sm" mt="xs">{asset.summary}</Text>}
                                {(asset.sourceRefs.length > 0 || asset.evidenceIds.length > 0) && (
                                    <Text className={styles.sourceEvidence} size="xs" mt="xs">
                                        {label(t, 'mod_archive.tree.evidence', 'Evidence')}: {[...asset.sourceRefs, ...asset.evidenceIds].join(' · ')}
                                    </Text>
                                )}
                            </Paper>
                        ))}
                    </div>
                </details>
            ))}
        </Paper>
    );
};

const ContextGroups = ({ preview, t }) => {
    if (!preview.hasEventContext) {
        const message = preview.route === 'reference_asset'
            ? label(t, 'mod_archive.tree.reference_no_context', 'Reference assets do not receive event-chain context.')
            : label(t, 'mod_archive.tree.no_event_context', 'No final event context is currently linked to this unit.');
        return <div className={styles.contextNotice} data-testid="context-tree-no-event-context">{message}</div>;
    }
    return (
        <Stack gap="sm" data-testid="context-tree-event-context">
            {preview.groups.map((group) => (
                <Paper className={styles.contextGroup} key={group.groupId} withBorder>
                    <Group justify="space-between" align="flex-start">
                        <div>
                            <Text fw={700}>{group.groupLabel}</Text>
                            <Text className={styles.muted} size="xs">{group.storyLabel}</Text>
                        </div>
                        <Badge size="xs" variant="outline">{group.fragments.length}</Badge>
                    </Group>
                    <ol className={styles.contextBullets}>
                        {group.fragments.map((fragment) => (
                            <li className={styles.contextBullet} key={fragment.id}>{fragment.summary}</li>
                        ))}
                    </ol>
                </Paper>
            ))}
        </Stack>
    );
};

export const ContextArchiveTreePreview = ({ tree, selectedUnitId, onUnitChange, selectedFragmentId, t }) => {
    const unitOptions = useMemo(() => getTreeUnitOptions(tree), [tree]);
    const unitId = selectedUnitId || unitOptions[0]?.id || null;
    const preview = useMemo(
        () => buildNarrativeUnitPreview(tree, unitId),
        [tree, unitId],
    );
    const selectedFragment = selectedFragmentId ? tree.fragments?.[selectedFragmentId] : null;
    const options = unitOptions.map((unit) => ({ value: unit.id, label: unit.label }));
    return (
        <Paper className={styles.previewPanel} p="md" withBorder data-remis-surface="paper" data-testid="context-tree-preview">
            <div className={styles.previewHeader}>
                <div>
                    <Text className={styles.summaryEyebrow}>{label(t, 'mod_archive.tree.preview_eyebrow', 'DELIVERY PREVIEW')}</Text>
                    <Title order={4}>{label(t, 'mod_archive.tree.preview_title', 'Final narrative-unit context')}</Title>
                    <Text className={styles.muted} size="sm">
                        {label(t, 'mod_archive.tree.preview_desc', 'Preview the ordered event context delivered to one narrative unit.')}
                    </Text>
                </div>
                <Group gap="xs" wrap="wrap">
                    {preview && <Badge variant="light">{preview.groups.length} {label(t, 'mod_archive.tree.groups_short', 'groups')}</Badge>}
                    <Badge variant="outline">{tree.version}</Badge>
                </Group>
            </div>
            <SelectedFragmentPanel fragment={selectedFragment} t={t} />
            {options.length === 0 ? (
                <Text className={styles.muted} size="sm">
                    {label(t, 'mod_archive.tree.no_narrative_units', 'No narrative units are available for preview.')}
                </Text>
            ) : (
                <Select
                    className={styles.previewSelect}
                    label={label(t, 'mod_archive.tree.preview_unit', 'Narrative unit')}
                    value={unitId}
                    data={options}
                    onChange={onUnitChange}
                    searchable
                    allowDeselect={false}
                    data-testid="context-tree-preview-unit"
                />
            )}
            {preview && (
                <>
                    {tree.projectSummary && (
                        <div className={styles.contextNotice} data-remis-surface="paper">
                            <Text fw={600}>{label(t, 'mod_archive.tree.project_summary', 'Project summary')}</Text>
                            <Text size="sm">{tree.projectSummary}</Text>
                        </div>
                    )}
                    <ContextGroups preview={preview} t={t} />
                </>
            )}
            <ReferenceAssetPanel tree={tree} t={t} />
        </Paper>
    );
};

export default ContextArchiveTreePreview;
