import React, { useMemo, useRef, useState } from 'react';
import {
    closestCenter,
    DndContext,
    DragOverlay,
    KeyboardSensor,
    PointerSensor,
    useDraggable,
    useDroppable,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Badge, Button, Paper, Text, TextInput, Title } from '@mantine/core';
import { IconGripVertical, IconPlus, IconTrash } from '@tabler/icons-react';

import styles from './PublishedContextWorkbench.module.css';

const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });
const groupDropId = (groupId) => `group:${groupId}`;
const fragmentDropId = (fragmentId) => `fragment:${fragmentId}`;

const fragmentIdFromDropId = (value) => String(value || '').replace(/^fragment:/, '');

const getGroupForFragment = (groups, fragmentId) => groups.find((group) => (
    group.fragmentIds.includes(fragmentId)
));

const FragmentCard = ({
    fragment,
    index,
    selected,
    showSummary,
    onSelect,
    onNativeDragStart,
}) => {
    const {
        attributes,
        listeners,
        setNodeRef: setDragNodeRef,
        transform,
        isDragging,
    } = useDraggable({
        id: fragment.id,
        data: { type: 'fragment', fragmentId: fragment.id },
    });
    const { setNodeRef: setDropNodeRef, isOver } = useDroppable({
        id: fragmentDropId(fragment.id),
        data: { type: 'fragment', fragmentId: fragment.id },
    });
    const setNodeRef = (node) => {
        setDragNodeRef(node);
        setDropNodeRef(node);
    };
    const style = transform ? { transform: CSS.Translate.toString(transform) } : undefined;
    return (
        <button
            ref={setNodeRef}
            type="button"
            className={styles.fragmentCard}
            style={style}
            data-selected={selected ? 'true' : 'false'}
            data-dragging={isDragging ? 'true' : 'false'}
            data-drag-over={isOver ? 'true' : 'false'}
            data-testid={`published-context-fragment-${fragment.id}`}
            aria-label={fragment.label}
            {...attributes}
            {...listeners}
            onClick={() => onSelect(fragment.id)}
            onDragStart={(event) => onNativeDragStart(event, fragment.id)}
        >
            <IconGripVertical className={styles.dragHandle} size={15} aria-hidden="true" />
            <span className={styles.fragmentOrder}>{String(index + 1).padStart(2, '0')}</span>
            <span className={styles.fragmentBody}>
                <span className={styles.fragmentLabel}>{fragment.label}</span>
                {showSummary && <span className={styles.fragmentSummary}>{fragment.summary || '—'}</span>}
            </span>
            <Badge size="xs" variant="outline">{fragment.unitIds.length}</Badge>
        </button>
    );
};

const GroupColumn = ({
    group,
    fragments,
    selectedFragmentId,
    focused,
    onSelect,
    onSelectGroup,
    onDeleteGroup,
    onNativeDragStart,
    onNativeDrop,
    t,
}) => {
    const { setNodeRef, isOver } = useDroppable({
        id: groupDropId(group.id),
        data: { type: 'group', groupId: group.id },
    });
    const [nativeDragOver, setNativeDragOver] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const handleNativeDrop = (event) => {
        event.preventDefault();
        setNativeDragOver(false);
        onNativeDrop(event, group.id);
    };
    return (
        <Paper
            ref={setNodeRef}
            className={`${styles.groupColumn} ${focused ? styles.focusedGroupColumn : ''}`}
            p="sm"
            withBorder
            data-remis-surface="paper"
            data-drag-over={isOver || nativeDragOver ? 'true' : 'false'}
            data-testid={`published-context-group-${group.id}`}
            onDragOver={(event) => {
                event.preventDefault();
                setNativeDragOver(true);
            }}
            onDragLeave={() => setNativeDragOver(false)}
            onDrop={handleNativeDrop}
        >
            <div className={styles.groupHeadingRow}>
                <button
                    type="button"
                    className={styles.groupHeadingButton}
                    data-testid={`published-context-group-header-${group.id}`}
                    onClick={() => onSelectGroup?.(group.id)}
                >
                    <span className={styles.groupHeadingCopy}>
                        <span className={styles.groupKicker}>{focused ? 'EVENT CHAIN' : 'CHAIN'}</span>
                        <span className={styles.groupTitle}>{group.label}</span>
                        {focused && group.summary && <span className={styles.groupSummary}>{group.summary}</span>}
                    </span>
                    <Badge size="sm" variant={focused ? 'light' : 'outline'}>{fragments.length}</Badge>
                </button>
                {focused && onDeleteGroup && (
                    confirmDelete ? (
                        <div className={styles.groupDeleteConfirm}>
                            <Button
                                size="compact-xs"
                                color="red"
                                onClick={() => onDeleteGroup(group.id)}
                            >
                                {text(t, 'mod_archive.tree_v2.confirm_delete_group', 'Delete chain')}
                            </Button>
                            <Button
                                size="compact-xs"
                                variant="default"
                                onClick={() => setConfirmDelete(false)}
                            >
                                {text(t, 'cancel', 'Cancel')}
                            </Button>
                        </div>
                    ) : (
                        <Button
                            size="compact-xs"
                            color="red"
                            variant="subtle"
                            aria-label={text(t, 'mod_archive.tree_v2.delete_group', 'Delete event chain')}
                            data-testid={`published-context-delete-group-${group.id}`}
                            onClick={() => setConfirmDelete(true)}
                        >
                            <IconTrash size={15} aria-hidden="true" />
                        </Button>
                    )
                )}
            </div>
            <div className={`${styles.fragmentList} ${focused ? styles.focusedFragmentList : ''}`}>
                {fragments.map((fragment, index) => (
                    <FragmentCard
                        key={fragment.id}
                        fragment={fragment}
                        index={index}
                        selected={fragment.id === selectedFragmentId}
                        showSummary={focused}
                        onSelect={onSelect}
                        onNativeDragStart={onNativeDragStart}
                    />
                ))}
                {fragments.length === 0 && (
                    <div className={styles.dropHint} data-drag-over={isOver ? 'true' : 'false'}>
                        {text(t, 'mod_archive.tree_v2.empty_group', 'Drop the first card here.')}
                    </div>
                )}
            </div>
        </Paper>
    );
};

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
    onSelect,
    onSelectGroup,
    onClearSelection,
    onCreateGroup,
    onDeleteGroup,
    onMoveFragment,
    t,
}) => {
    const nativeDragIdRef = useRef(null);
    const [activeFragmentId, setActiveFragmentId] = useState(null);
    const [showCreateGroup, setShowCreateGroup] = useState(false);
    const [newGroupLabel, setNewGroupLabel] = useState('');
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
        useSensor(KeyboardSensor),
    );
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
    const supportFragments = useMemo(() => tree.referenceAssets
        .map((asset) => tree.fragments[asset.fragmentId || asset.id])
        .filter(Boolean), [tree.fragments, tree.referenceAssets]);
    const eventGroups = stories.flatMap((story) => story.groupIds
        .map((groupId) => tree.groups.find((group) => group.id === groupId))
        .filter(Boolean)
        .map((group) => ({
            group,
            fragments: group.fragmentIds.map((id) => tree.fragments[id]).filter(Boolean),
            selectable: true,
        })));
    const overviewItems = [
        ...eventGroups,
        ...(unassigned.length > 0 ? [{
            group: { id: 'group-unassigned', label: text(t, 'mod_archive.tree_v2.unassigned', 'Needs placement'), fragmentIds: unassigned.map((fragment) => fragment.id) },
            fragments: unassigned,
            selectable: false,
        }] : []),
        ...(supportFragments.length > 0 ? [{
            group: { id: 'group-support', label: text(t, 'mod_archive.tree_v2.supporting_text', 'Supporting text'), fragmentIds: supportFragments.map((fragment) => fragment.id) },
            fragments: supportFragments,
            selectable: false,
        }] : []),
    ];
    const allFragments = useMemo(() => Object.values(tree.fragments), [tree.fragments]);
    const activeFragment = activeFragmentId
        ? allFragments.find((fragment) => fragment.id === activeFragmentId)
        : null;

    const handleDragEnd = ({ active, over }) => {
        setActiveFragmentId(null);
        if (!over) return;
        const fragmentId = String(active.id);
        const overId = String(over.id);
        const overFragmentId = overId.startsWith('fragment:') ? fragmentIdFromDropId(overId) : null;
        const targetGroupId = overId.startsWith('group:')
            ? overId.replace(/^group:/, '')
            : getGroupForFragment(tree.groups, overFragmentId)?.id;
        if (!targetGroupId || (overFragmentId === fragmentId && targetGroupId === getGroupForFragment(tree.groups, fragmentId)?.id)) return;
        onMoveFragment({ fragmentId, targetGroupId, overFragmentId });
    };

    const handleNativeDragStart = (event, fragmentId) => {
        nativeDragIdRef.current = fragmentId;
        event.dataTransfer?.setData('text/plain', fragmentId);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
    };

    const handleNativeDrop = (event, groupId) => {
        const fragmentId = event.dataTransfer?.getData('text/plain') || nativeDragIdRef.current;
        if (fragmentId) onMoveFragment({ fragmentId, targetGroupId: groupId });
        nativeDragIdRef.current = null;
    };

    const renderGroup = (group, fragments, selectable = true) => (
        <GroupColumn
            key={group.id}
            group={group}
            fragments={fragments}
            selectedFragmentId={selectedFragmentId}
            focused={focused}
            onSelect={onSelect}
            onSelectGroup={selectable ? onSelectGroup : null}
            onDeleteGroup={selectable ? onDeleteGroup : null}
            onNativeDragStart={handleNativeDragStart}
            onNativeDrop={handleNativeDrop}
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
        <Paper className={styles.mapPanel} p="md" withBorder data-remis-surface="surface" data-testid="published-context-map" data-view={focused ? 'focused' : 'overview'}>
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
                        <button type="button" className={styles.mapBack} onClick={onClearSelection}>
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
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={({ active }) => setActiveFragmentId(String(active.id))}
                onDragCancel={() => setActiveFragmentId(null)}
                onDragEnd={handleDragEnd}
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
                                {overviewItems.map(({ group, fragments, selectable }) => renderGroup(group, fragments, selectable))}
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
