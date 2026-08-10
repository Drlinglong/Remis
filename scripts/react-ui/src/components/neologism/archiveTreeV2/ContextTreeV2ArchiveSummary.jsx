import React, { useMemo } from 'react';
import { Alert, Badge, Button, Group, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { createContextArchiveTreeApi } from './contextArchiveTreeApi';
import { normalizeArchiveTree } from './contextArchiveTreeModel';
import { useContextArchiveTree } from './useContextArchiveTree';
import { useContextWorkbenchSelection } from './useContextWorkbenchSelection';
import PublishedContextEntitySummary from './PublishedContextEntitySummary';
import PublishedContextEventDetail from './PublishedContextEventDetail';
import PublishedContextMap from './PublishedContextMap';
import styles from './PublishedContextWorkbench.module.css';

const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });

export const ContextTreeV2ArchiveSummary = ({ tree, mode = 'published' }) => {
    const { t } = useTranslation();
    const adapter = useMemo(() => createContextArchiveTreeApi(), []);
    const archiveState = useContextArchiveTree({
        initialTree: tree,
        adapter,
        enabled: false,
        projectId: tree?.project_id || tree?.projectId,
        releaseId: tree?.release_id || tree?.releaseId,
        draftId: tree?.draft_id || tree?.draftId,
        mode,
    });
    const normalizedTree = archiveState.tree || normalizeArchiveTree(tree);
    const selection = useContextWorkbenchSelection({
        groups: normalizedTree.groups,
        fragments: normalizedTree.fragments,
        identity: tree?.release_id || tree?.releaseId,
    });

    const deleteGroup = (groupId) => {
        archiveState.deleteGroup(groupId);
        selection.clearSelection();
    };

    return (
        <Stack className={styles.page} gap="md" data-testid={`context-tree-v2-${mode}`} data-remis-surface="canvas">
            <header className={styles.pageHeader}>
                <div className={styles.titleBlock}>
                    <Text className={styles.eyebrow}>{text(t, 'mod_archive.tree_v2.eyebrow', 'CONTEXT ARCHIVE')}</Text>
                    <Title order={1} className={styles.title}>{normalizedTree.title}</Title>
                    {normalizedTree.projectSummary && (
                        <Text className={styles.projectSummary} size="sm">{normalizedTree.projectSummary}</Text>
                    )}
                </div>
                <Group className={styles.pageActions} gap="xs" wrap="wrap">
                    <Badge variant={mode === 'published' ? 'light' : 'outline'}>
                        {mode === 'published'
                            ? text(t, 'mod_archive.tree_v2.published_status', 'Published archive')
                            : text(t, 'mod_archive.tree_v2.preview_status', 'Draft preview')}
                    </Badge>
                    {archiveState.dirty && <Text className={styles.statusText}>{text(t, 'mod_archive.tree_v2.unsaved', 'Unsaved relationship changes')}</Text>}
                    {archiveState.dirty && archiveState.canSave && (
                        <>
                            <Button size="xs" loading={archiveState.saving} onClick={archiveState.save}>
                                {text(t, 'mod_archive.tree_v2.save', 'Save map')}</Button>
                            <Button size="xs" variant="default" onClick={archiveState.reset} disabled={archiveState.saving}>
                                {text(t, 'mod_archive.tree_v2.reset', 'Reset')}</Button>
                        </>
                    )}
                </Group>
            </header>
            {archiveState.error && (
                <Alert color="red" data-testid="published-context-error">
                    {archiveState.error}
                </Alert>
            )}
            <div className={styles.workbench} data-testid="published-context-workbench">
                <PublishedContextMap
                    tree={normalizedTree}
                    selectedFragmentId={selection.selectedFragmentId}
                    selectedGroupId={selection.selectedGroupId}
                    transitionPhase={selection.transitionPhase}
                    onSelect={selection.selectFragment}
                    onSelectGroup={selection.selectGroup}
                    onClearSelection={selection.clearSelection}
                    onCreateGroup={archiveState.createGroup}
                    onRenameGroup={archiveState.renameGroup}
                    onDeleteGroup={deleteGroup}
                    onMoveFragment={archiveState.moveFragment}
                    t={t}
                />
                <PublishedContextEventDetail
                    tree={normalizedTree}
                    selectedFragmentId={selection.selectedFragmentId}
                    selectedGroupId={selection.selectedGroupId}
                    onClearSelection={selection.clearSelection}
                    onSelectFragment={selection.selectFragment}
                    onSetFragmentDisposition={archiveState.setFragmentDisposition}
                    t={t}
                />
            </div>
            <PublishedContextEntitySummary tree={tree} normalizedTree={normalizedTree} t={t} />
        </Stack>
    );
};

export default ContextTreeV2ArchiveSummary;
