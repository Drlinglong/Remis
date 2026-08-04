import React, { useEffect, useMemo, useState } from 'react';
import {
    Badge,
    Button,
    Group,
    Loader,
    Paper,
    Text,
    Title,
} from '@mantine/core';
import { IconDeviceFloppy, IconInfoCircle, IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import ContextArchiveTreeCanvas from './ContextArchiveTreeCanvas';
import ContextArchiveTreePreview from './ContextArchiveTreePreview';
import { getFirstNarrativeUnitId, getTreeUnitOptions } from './contextArchiveTreeModel';
import { useContextArchiveTree } from './useContextArchiveTree';
import styles from './ContextArchiveTree.module.css';

const label = (t, key, fallback, options = {}) => t(key, { ...options, defaultValue: fallback });

const EmptyTree = ({ t }) => (
    <Paper className={styles.emptyPanel} p="md" withBorder data-testid="context-tree-unavailable">
        <Group align="flex-start" wrap="nowrap">
            <IconInfoCircle size={22} aria-hidden="true" />
            <div>
                <Text fw={700}>{label(t, 'mod_archive.tree.unavailable_title', 'Tree review is not available for this version.')}</Text>
                <Text className={styles.muted} size="sm">
                    {label(t, 'mod_archive.tree.unavailable_desc', 'The published archive remains readable. A v2 relationship payload is required before relationship editing can begin.')}
                </Text>
            </div>
        </Group>
    </Paper>
);

export const ContextArchiveTreeReview = ({
    projectId,
    releaseId,
    draftId,
    mode = 'published',
    treeData = null,
    adapter = null,
    onOpenDetails,
}) => {
    const { t } = useTranslation();
    const treeState = useContextArchiveTree({
        initialTree: treeData,
        adapter,
        enabled: Boolean(treeData || adapter),
        projectId,
        releaseId,
        draftId,
        mode,
    });
    const [selectedUnitId, setSelectedUnitId] = useState(null);
    const unitOptions = useMemo(() => getTreeUnitOptions(treeState.tree), [treeState.tree]);
    useEffect(() => {
        if (!unitOptions.some((unit) => unit.id === selectedUnitId)) {
            setSelectedUnitId(getFirstNarrativeUnitId(treeState.tree));
        }
    }, [selectedUnitId, treeState.tree, unitOptions]);

    return (
        <section className={styles.review} data-testid="context-tree-review">
            <Group className={styles.reviewHeader} justify="space-between" wrap="wrap">
                <div className={styles.reviewTitle}>
                    <Group gap="xs" align="center">
                        <Title order={3}>{label(t, 'mod_archive.tree.title', 'Context archive tree v2')}</Title>
                        <Badge variant="outline">{label(t, 'mod_archive.tree.relationship_draft', 'Relationship draft')}</Badge>
                    </Group>
                    <Text className={styles.reviewSubtitle} size="sm">
                        {label(t, 'mod_archive.tree.subtitle', 'Review stories, sibling event groups, and ordered fragments. Source evidence stays read-only.')}
                    </Text>
                </div>
                <Group gap="xs">
                    {treeState.canSave && (
                        <Button
                            size="sm"
                            leftSection={<IconDeviceFloppy size={15} />}
                            onClick={treeState.save}
                            loading={treeState.saving}
                            disabled={!treeState.dirty || treeState.saving}
                            data-testid="context-tree-save"
                        >
                            {label(t, 'mod_archive.tree.save', 'Save relationship draft')}
                        </Button>
                    )}
                    <Button
                        size="sm"
                        variant="subtle"
                        leftSection={<IconRefresh size={15} />}
                        onClick={treeState.canSave ? treeState.load : treeState.reset}
                        disabled={treeState.saving}
                        data-testid="context-tree-reset"
                    >
                        {label(t, 'mod_archive.tree.reset', 'Reset')}
                    </Button>
                </Group>
            </Group>
            <Group className={styles.status} gap="xs" mb="sm">
                <Badge variant="light">{treeState.tree.version}</Badge>
                {treeState.dirty && <Text className={styles.draftStatus} size="xs">{label(t, 'mod_archive.tree.unsaved', 'Unsaved local relationship changes')}</Text>}
                {!treeState.canSave && (
                    <Text size="xs">
                        {label(t, 'mod_archive.tree.adapter_pending', 'Persistence adapter pending integration; edits remain local in this view.')}
                    </Text>
                )}
                {treeState.error && <Text c="red" size="xs">{treeState.error}</Text>}
            </Group>
            {treeState.phase === 'loading' && (
                <Paper className={styles.emptyPanel} p="md" withBorder>
                    <Group><Loader size="sm" /><Text>{label(t, 'mod_archive.tree.loading', 'Loading relationship draft…')}</Text></Group>
                </Paper>
            )}
            {treeState.phase !== 'loading' && !treeState.tree.available && <EmptyTree t={t} />}
            {treeState.tree.available && (
                <div className={styles.canvas}>
                    <ContextArchiveTreeCanvas
                        tree={treeState.tree}
                        t={t}
                        onCreateStory={treeState.createStory}
                        onRenameStory={treeState.renameStory}
                        onDeleteStory={treeState.deleteStory}
                        onCreateGroup={treeState.createGroup}
                        onRenameGroup={treeState.renameGroup}
                        onDeleteGroup={treeState.deleteGroup}
                        onMoveFragment={treeState.moveFragment}
                        onReorderFragment={treeState.reorderFragment}
                        onSetFragmentDisposition={treeState.setFragmentDisposition}
                        onOpenDetails={onOpenDetails}
                    />
                    <ContextArchiveTreePreview
                        tree={treeState.tree}
                        selectedUnitId={selectedUnitId}
                        onUnitChange={setSelectedUnitId}
                        t={t}
                    />
                </div>
            )}
        </section>
    );
};

export default ContextArchiveTreeReview;
