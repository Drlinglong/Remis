import React, { useMemo, useState } from 'react';
import {
    closestCenter,
    DndContext,
    DragOverlay,
} from '@dnd-kit/core';
import { Badge, Button, Paper, Text, TextInput, Title } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';

import PublishedContextGroupColumn from './PublishedContextGroupColumn';
import styles from './PublishedContextWorkbench.module.css';
import { getGroupForFragment, useFragmentDrag } from './useFragmentDrag';

const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });
const StoryRail = ({ story, t }) => (
    <div className={styles.storyRail}>
        <span className={styles.storyKicker}>{text(t, 'mod_archive.tree_v2.story_label', 'STORY')}</span>
        <span className={styles.storyTitle}>{story?.label || text(t, 'mod_archive.tree_v2.story_fallback', 'Project structure')}</span>
    </div>
);

const PublishedContextMap = ({
    tree,
    selectedFragmentId,
    selectedGroupId,
    transitionPhase,
    onSelect,
    onSelectGroup,
    onClearSelection,
    onCreateGroup,
    onDeleteGroup,
    onMoveFragment,
    t,
}) => {
    const [showCreateGroup, setShowCreateGroup] = useState(false);
    const [newGroupLabel, setNewGroupLabel] = useState('');
    const drag = useFragmentDrag({ groups: tree.groups, onMoveFragment });
    const stories = tree.stories.length > 0 ? tree.stories : [{
        id: 'story-main',
        label: tree.title,
        groupIds: tree.groups.map((group) => group.id),
    }];
    const selectedGroup = tree.groups.find((group) => group.id === selectedGroupId);
    const focusedGroup = selectedGroup || getGroupForFragment(tree.groups, selectedFragmentId);
    const focused = Boolean(focusedGroup);
    const assigned = new Set(tree.groups.flatMap((group) => group.fragmentIds));
    const unassigned = Object.values(tree.fragments).filter((fragment) => (
        fragment.route === 'narrative' && !assigned.has(fragment.id)
    ));
    const supportFragments = useMemo(() => [...new Map(tree.referenceAssets
        .map((asset) => tree.fragments[asset.fragmentId || asset.id])
        .filter(Boolean)
        .map((fragment) => [fragment.id, fragment])).values()], [tree.fragments, tree.referenceAssets]);
    const eventGroups = stories.flatMap((story) => story.groupIds
        .map((groupId) => tree.groups.find((group) => group.id === groupId))
        .filter(Boolean)
        .map((group) => ({
            group,
            fragments: group.fragmentIds.map((id) => tree.fragments[id]).filter(Boolean),
            selectable: true,
            kind: 'event',
        })));
    const overviewItems = [
        ...eventGroups,
        ...(supportFragments.length > 0 ? [{
            group: { id: 'group-support', label: text(t, 'mod_archive.tree_v2.supporting_text', 'Supporting text'), fragmentIds: supportFragments.map((fragment) => fragment.id) },
            fragments: supportFragments,
            selectable: false,
            kind: 'supporting',
        }] : []),
        ...(unassigned.length > 0 ? [{
            group: { id: 'group-unassigned', label: text(t, 'mod_archive.tree_v2.unassigned', 'Needs placement'), fragmentIds: unassigned.map((fragment) => fragment.id) },
            fragments: unassigned,
            selectable: false,
            kind: 'needs-placement',
        }] : []),
    ];
    const allFragments = useMemo(() => Object.values(tree.fragments), [tree.fragments]);
    const activeFragment = drag.activeFragmentId
        ? allFragments.find((fragment) => fragment.id === drag.activeFragmentId)
        : null;

    const renderGroup = (group, fragments, selectable = true, kind = 'event') => (
        <PublishedContextGroupColumn
            key={group.id}
            group={group}
            fragments={fragments}
            selectedFragmentId={selectedFragmentId}
            focused={focused}
            onSelect={onSelect}
            onSelectGroup={selectable ? onSelectGroup : null}
            onDeleteGroup={selectable ? onDeleteGroup : null}
            kind={kind}
            t={t}
        />
    );

    const handleCreateGroup = (event) => {
        event.preventDefault();
        const label = newGroupLabel.trim();
        const storyId = stories[0]?.id;
        if (!label || !storyId || !onCreateGroup) return;
        onCreateGroup({ storyId, label });
        setNewGroupLabel('');
        setShowCreateGroup(false);
    };

    return (
        <Paper
            className={styles.mapPanel}
            p="md"
            withBorder
            data-remis-surface="surface"
            data-testid="published-context-map"
            data-view={focused ? 'focused' : 'overview'}
            data-transition={transitionPhase}
        >
            <header className={styles.panelHeader}>
                <div>
                    <Text className={styles.eyebrow}>{text(t, 'mod_archive.tree_v2.map_eyebrow', 'RELATIONSHIP MAP')}</Text>
                    <Title order={2} className={styles.panelTitle}>
                        {focused ? focusedGroup.label : text(t, 'mod_archive.tree_v2.overview_title', 'Structure overview')}
                    </Title>
                    <Text className={styles.panelDescription} size="sm">
                        {focused
                            ? text(t, 'mod_archive.tree_v2.focused_map_desc', 'Inspect this event chain in order. Descriptions are shown here so the relationship can be checked before saving.')
                            : text(t, 'mod_archive.tree_v2.overview_desc', 'Project structure at a glance. Cards show titles only; choose an event chain or card to inspect its details.')}
                    </Text>
                </div>
                <div className={styles.panelHeaderActions}>
                    {!focused && onCreateGroup && (
                        <Button
                            size="xs"
                            variant="light"
                            data-testid="published-context-add-group"
                            leftSection={<IconPlus size={15} aria-hidden="true" />}
                            onClick={() => setShowCreateGroup((current) => !current)}
                        >
                            {text(t, 'mod_archive.tree_v2.add_group', 'Add event chain')}
                        </Button>
                    )}
                    {focused ? (
                        <button
                            type="button"
                            className={styles.mapBack}
                            data-remis-action="secondary"
                            onClick={onClearSelection}
                        >
                            {text(t, 'mod_archive.tree_v2.back_to_overview', 'Back to overview')}
                        </button>
                    ) : (
                        <Badge variant="outline">{tree.groups.length}</Badge>
                    )}
                </div>
            </header>
            {showCreateGroup && !focused && (
                <form className={styles.createGroupForm} onSubmit={handleCreateGroup}>
                    <TextInput
                        className={styles.createGroupInput}
                        label={text(t, 'mod_archive.tree_v2.new_group', 'New event chain')}
                        placeholder={text(t, 'mod_archive.tree_v2.new_group_placeholder', 'Event chain name')}
                        value={newGroupLabel}
                        onChange={(event) => setNewGroupLabel(event.currentTarget.value)}
                        autoFocus
                    />
                    <div className={styles.createGroupActions}>
                        <Button type="submit" size="xs" disabled={!newGroupLabel.trim()}>
                            {text(t, 'mod_archive.tree_v2.add_group', 'Add event chain')}
                        </Button>
                        <Button type="button" size="xs" variant="default" onClick={() => setShowCreateGroup(false)}>
                            {text(t, 'cancel', 'Cancel')}
                        </Button>
                    </div>
                </form>
            )}
            <DndContext
                sensors={drag.sensors}
                collisionDetection={closestCenter}
                onDragStart={drag.handleDragStart}
                onDragCancel={drag.handleDragCancel}
                onDragEnd={drag.handleDragEnd}
            >
                {focused ? (
                    <div className={styles.focusedGraph}>
                        <div className={styles.focusedStoryLine}>
                            <StoryRail story={stories.find((story) => story.groupIds.includes(focusedGroup.id))} t={t} />
                        </div>
                        <div className={styles.focusedColumn}>
                            {renderGroup(focusedGroup, focusedGroup.fragmentIds.map((id) => tree.fragments[id]).filter(Boolean))}
                        </div>
                    </div>
                ) : (
                    <div className={styles.overviewGraph}>
                        <div className={styles.projectRoot} data-testid="published-context-project-root">
                            <Text className={styles.rootLabel}>{text(t, 'mod_archive.tree_v2.project_root', 'PROJECT ROOT')}</Text>
                            <Text className={styles.rootTitle}>{tree.title}</Text>
                        </div>
                        <div className={styles.rootConnector} aria-hidden="true" />
                        <StoryRail story={stories[0]} t={t} />
                        <div className={styles.overviewRailViewport}>
                            <div
                                className={styles.groupGrid}
                                style={{ '--chain-count': Math.max(1, overviewItems.length) }}
                            >
                                {overviewItems.map(({ group, fragments, selectable, kind }) => renderGroup(group, fragments, selectable, kind))}
                            </div>
                        </div>
                    </div>
                )}
                <DragOverlay>
                    {activeFragment ? <div className={styles.dragOverlay}>{activeFragment.label}</div> : null}
                </DragOverlay>
            </DndContext>
            {tree.groups.length === 0 && unassigned.length === 0 && supportFragments.length === 0 && (
                <div className={styles.emptyMap}>
                    <Text fw={700}>{text(t, 'mod_archive.tree_v2.empty_map_title', 'No event chains yet')}</Text>
                    <Text size="sm">{text(t, 'mod_archive.tree_v2.empty_map_desc', 'This release does not contain relationship cards to display.')}</Text>
                </div>
            )}
        </Paper>
    );
};

export default PublishedContextMap;
