import React, { useEffect, useMemo, useState } from 'react';
import {
    Badge,
    Button,
    Group,
    Paper,
    Select,
    Stack,
    Text,
    TextInput,
    Title,
} from '@mantine/core';
import {
    IconArrowDown,
    IconArrowUp,
    IconGripVertical,
    IconPlus,
    IconTrash,
} from '@tabler/icons-react';

import { TREE_ROUTE, getGroupById } from './contextArchiveTreeModel';
import styles from './ContextArchiveTree.module.css';

const FRAGMENT_MIME = 'application/x-remis-context-fragment';

const label = (t, key, fallback, options = {}) => t(key, { ...options, defaultValue: fallback });

const routeOptions = (t) => [
    { value: TREE_ROUTE.NARRATIVE, label: label(t, 'mod_archive.tree.route_narrative', 'Narrative') },
    { value: TREE_ROUTE.UNRESOLVED, label: label(t, 'mod_archive.tree.route_unresolved', 'Unresolved') },
    { value: TREE_ROUTE.REFERENCE_ASSET, label: label(t, 'mod_archive.tree.route_reference_asset', 'Reference asset') },
];

const RenameInput = ({ value, labelText, onCommit }) => {
    const [draft, setDraft] = useState(value);
    useEffect(() => setDraft(value), [value]);
    const commit = () => {
        const next = draft.trim();
        if (next && next !== value) onCommit(next);
        else setDraft(value);
    };
    return (
        <TextInput
            className={styles.storyTitle}
            size="sm"
            value={draft}
            aria-label={labelText}
            onChange={(event) => setDraft(event.currentTarget.value)}
            onBlur={commit}
            onKeyDown={(event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    commit();
                    event.currentTarget.blur();
                }
                if (event.key === 'Escape') {
                    setDraft(value);
                    event.currentTarget.blur();
                }
            }}
        />
    );
};

const CreateForm = ({ labelText, placeholder, value, onChange, onSubmit, onCancel, t }) => (
    <div className={styles.inlineForm}>
        <TextInput
            className={styles.inlineInput}
            size="sm"
            label={labelText}
            placeholder={placeholder}
            value={value}
            onChange={(event) => onChange(event.currentTarget.value)}
            onKeyDown={(event) => {
                if (event.key === 'Enter') onSubmit();
                if (event.key === 'Escape') onCancel();
            }}
            autoFocus
        />
        <Button size="sm" onClick={onSubmit} disabled={!value.trim()}>{label(t, 'save', 'Create')}</Button>
        <Button size="sm" variant="subtle" onClick={onCancel}>{label(t, 'cancel', 'Cancel')}</Button>
    </div>
);

const getDraggedFragmentId = (event) => event.dataTransfer?.getData(FRAGMENT_MIME)
    || event.dataTransfer?.getData('text/plain')
    || null;

const FragmentNode = ({
    fragment,
    groupId,
    groupOptions,
    index,
    groupLength,
    t,
    onMoveFragment,
    onReorderFragment,
    onSetFragmentDisposition,
    onOpenDetails,
    onDrop,
}) => {
    const coverage = fragment.coverage?.local_unit_coverage
        ?? fragment.coverage?.unit_count
        ?? fragment.unitIds.length;
    const evidenceCount = fragment.evidenceIds.length;
    return (
        <li
            className={styles.fragment}
            draggable
            onDragStart={(event) => {
                event.dataTransfer?.setData(FRAGMENT_MIME, fragment.id);
                event.dataTransfer?.setData('text/plain', fragment.id);
                if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => onDrop(event, groupId, fragment.id)}
            data-testid={`context-tree-fragment-${fragment.id}`}
        >
            <Group className={styles.fragmentHeader} justify="space-between" wrap="nowrap">
                <Group gap="xs" wrap="nowrap" className={styles.fragmentLabel}>
                    <IconGripVertical className={styles.dragHandle} size={16} aria-hidden="true" />
                    <Text fw={700} className={styles.fragmentLabel}>{fragment.label}</Text>
                </Group>
                <Group gap="xs" wrap="wrap">
                    <Badge size="xs" variant="outline">{fragment.tier}</Badge>
                    <Badge size="xs" variant="light">{fragment.route}</Badge>
                </Group>
            </Group>
            <Text className={styles.fragmentSummary} size="sm">{fragment.summary}</Text>
            <Text className={styles.muted} size="xs">
                {label(t, 'mod_archive.tree.coverage', 'Coverage')}: {coverage}
                {' · '}
                {label(t, 'mod_archive.tree.evidence', 'Evidence')}: {evidenceCount}
                {' · '}
                {label(t, 'mod_archive.tree.units', 'Units')}: {fragment.unitIds.length}
            </Text>
            <div className={styles.fragmentActions}>
                <Select
                    className={styles.fragmentGroup}
                    size="xs"
                    label={label(t, 'mod_archive.tree.move_group', 'Move to group')}
                    value={groupId || null}
                    data={groupOptions}
                    placeholder={label(t, 'mod_archive.tree.choose_group', 'Choose a group')}
                    onChange={(targetGroupId) => targetGroupId && onMoveFragment({
                        fragmentId: fragment.id,
                        targetGroupId,
                    })}
                    searchable
                    clearable={false}
                />
                <Select
                    className={styles.fragmentRoute}
                    size="xs"
                    label={label(t, 'mod_archive.tree.route', 'Route')}
                    value={fragment.route === TREE_ROUTE.NO_CONTEXT ? TREE_ROUTE.UNRESOLVED : fragment.route}
                    data={routeOptions(t)}
                    onChange={(route) => route && onSetFragmentDisposition(fragment.id, route, {
                        targetGroupId: groupId,
                    })}
                    clearable={false}
                />
                {groupId && (
                    <Group gap={2} wrap="nowrap">
                        <Button
                            size="compact-xs"
                            variant="subtle"
                            aria-label={label(t, 'mod_archive.tree.move_up', 'Move fragment up')}
                            onClick={() => onReorderFragment({ fragmentId: fragment.id, groupId, index: index - 1 })}
                            disabled={index <= 0}
                        >
                            <IconArrowUp size={14} aria-hidden="true" />
                        </Button>
                        <Button
                            size="compact-xs"
                            variant="subtle"
                            aria-label={label(t, 'mod_archive.tree.move_down', 'Move fragment down')}
                            onClick={() => onReorderFragment({ fragmentId: fragment.id, groupId, index: index + 1 })}
                            disabled={index >= groupLength - 1}
                        >
                            <IconArrowDown size={14} aria-hidden="true" />
                        </Button>
                    </Group>
                )}
                {onOpenDetails && (
                    <Button size="xs" variant="subtle" onClick={() => onOpenDetails(fragment)}>
                        {label(t, 'mod_archive.tree.open_details', 'Open details')}
                    </Button>
                )}
            </div>
        </li>
    );
};

const GroupNode = ({
    group,
    groupOptions,
    fragments,
    t,
    onRename,
    onDelete,
    onMoveFragment,
    onReorderFragment,
    onSetFragmentDisposition,
    onOpenDetails,
    onDrop,
}) => (
    <li className={styles.group} data-testid={`context-tree-group-${group.id}`}>
        <Group className={styles.groupHeader} justify="space-between" wrap="wrap">
            <RenameInput
                value={group.label}
                labelText={label(t, 'mod_archive.tree.rename_group', 'Rename event group')}
                onCommit={onRename}
            />
            <div className={styles.containerActions}>
                <Badge variant="outline">{group.fragmentIds.length}</Badge>
                <Button
                    size="compact-xs"
                    color="red"
                    variant="subtle"
                    aria-label={label(t, 'mod_archive.tree.delete_group', 'Delete event group')}
                    onClick={onDelete}
                >
                    <IconTrash size={14} aria-hidden="true" />
                </Button>
            </div>
        </Group>
        {group.summary && <Text className={styles.summaryText} size="xs">{group.summary}</Text>}
        <div
            className={styles.dropTarget}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => onDrop(event, group.id, null)}
            data-testid={`context-tree-drop-${group.id}`}
        >
            <ul className={styles.fragmentList}>
                {fragments.map((fragment, index) => (
                    <FragmentNode
                        fragment={fragment}
                        groupId={group.id}
                        groupOptions={groupOptions}
                        index={index}
                        groupLength={fragments.length}
                        key={fragment.id}
                        t={t}
                        onMoveFragment={onMoveFragment}
                        onReorderFragment={onReorderFragment}
                        onSetFragmentDisposition={onSetFragmentDisposition}
                        onOpenDetails={onOpenDetails}
                        onDrop={onDrop}
                    />
                ))}
            </ul>
            {fragments.length === 0 && (
                <Text className={styles.helperText} size="xs">
                    {label(t, 'mod_archive.tree.drop_here', 'Drop a narrative fragment here.')}
                </Text>
            )}
        </div>
    </li>
);

const StoryNode = ({
    story,
    groups,
    groupOptions,
    t,
    onRename,
    onDelete,
    onCreateGroup,
    onRenameGroup,
    onDeleteGroup,
    onMoveFragment,
    onReorderFragment,
    onSetFragmentDisposition,
    onOpenDetails,
    onDrop,
}) => {
    const [creatingGroup, setCreatingGroup] = useState(false);
    const [groupLabel, setGroupLabel] = useState('');
    const submitGroup = () => {
        if (!groupLabel.trim()) return;
        onCreateGroup({ storyId: story.id, label: groupLabel.trim() });
        setGroupLabel('');
        setCreatingGroup(false);
    };
    return (
        <li className={styles.story} role="treeitem" aria-label={story.label}>
            <Group className={styles.storyHeader} justify="space-between" wrap="wrap">
                <RenameInput
                    value={story.label}
                    labelText={label(t, 'mod_archive.tree.rename_story', 'Rename story')}
                    onCommit={(value) => onRename(story.id, value)}
                />
                <div className={styles.containerActions}>
                    <Badge variant="light">{story.groupIds.length}</Badge>
                    <Button size="xs" variant="subtle" onClick={() => setCreatingGroup(true)}>
                        <IconPlus size={14} aria-hidden="true" />
                        {label(t, 'mod_archive.tree.add_group', 'Add group')}
                    </Button>
                    <Button
                        size="compact-xs"
                        color="red"
                        variant="subtle"
                        aria-label={label(t, 'mod_archive.tree.delete_story', 'Delete story')}
                        onClick={() => onDelete(story.id)}
                    >
                        <IconTrash size={14} aria-hidden="true" />
                    </Button>
                </div>
            </Group>
            {story.summary && <Text className={styles.summaryText} size="xs">{story.summary}</Text>}
            {creatingGroup && (
                <CreateForm
                    labelText={label(t, 'mod_archive.tree.new_group', 'New event group')}
                    placeholder={label(t, 'mod_archive.tree.new_group_placeholder', 'Group name')}
                    value={groupLabel}
                    onChange={setGroupLabel}
                    onSubmit={submitGroup}
                    onCancel={() => setCreatingGroup(false)}
                    t={t}
                />
            )}
            <ul className={styles.groupList} role="group">
                {groups.map((group) => (
                    <GroupNode
                        group={group}
                        groupOptions={groupOptions}
                        fragments={group.fragmentIds.map((id) => id).filter(Boolean)}
                        key={group.id}
                        t={t}
                        onRename={(value) => onRenameGroup(group.id, value)}
                        onDelete={() => onDeleteGroup(group.id)}
                        onMoveFragment={onMoveFragment}
                        onReorderFragment={onReorderFragment}
                        onSetFragmentDisposition={onSetFragmentDisposition}
                        onOpenDetails={onOpenDetails}
                        onDrop={onDrop}
                    />
                ))}
            </ul>
        </li>
    );
};

export const ContextArchiveTreeCanvas = ({
    tree,
    t,
    onCreateStory,
    onRenameStory,
    onDeleteStory,
    onCreateGroup,
    onRenameGroup,
    onDeleteGroup,
    onMoveFragment,
    onReorderFragment,
    onSetFragmentDisposition,
    onOpenDetails,
}) => {
    const [creatingStory, setCreatingStory] = useState(false);
    const [storyLabel, setStoryLabel] = useState('');
    const groupsByStory = useMemo(() => new Map(tree.stories.map((story) => [
        story.id,
        story.groupIds.map((groupId) => getGroupById(tree, groupId)).filter(Boolean),
    ])), [tree]);
    const allGroups = tree.groups.map((group) => ({ value: group.id, label: group.label }));
    const fragmentsById = tree.fragments;
    const unresolved = tree.unresolvedFragmentIds
        .map((fragmentId) => fragmentsById[fragmentId])
        .filter(Boolean);
    const submitStory = () => {
        if (!storyLabel.trim()) return;
        onCreateStory({ label: storyLabel.trim() });
        setStoryLabel('');
        setCreatingStory(false);
    };
    const handleDrop = (event, targetGroupId, overFragmentId) => {
        event.preventDefault();
        const fragmentId = getDraggedFragmentId(event);
        if (!fragmentId || !targetGroupId) return;
        onMoveFragment({ fragmentId, targetGroupId, overFragmentId });
    };
    return (
        <Paper className={styles.treePanel} p="md" withBorder data-testid="context-tree-canvas">
            <Group className={styles.canvasHeader} justify="space-between" wrap="wrap">
                <div>
                    <Title order={4}>{label(t, 'mod_archive.tree.relationships_title', 'Stories and event groups')}</Title>
                    <Text className={styles.helperText} size="sm">
                        {label(t, 'mod_archive.tree.relationships_desc', 'Groups are siblings without time-order semantics; fragment order is meaningful within a group.')}
                    </Text>
                </div>
                <Button size="sm" variant="light" onClick={() => setCreatingStory(true)}>
                    <IconPlus size={15} aria-hidden="true" />
                    {label(t, 'mod_archive.tree.add_story', 'Add story')}
                </Button>
            </Group>
            {creatingStory && (
                <CreateForm
                    labelText={label(t, 'mod_archive.tree.new_story', 'New story')}
                    placeholder={label(t, 'mod_archive.tree.new_story_placeholder', 'Story name')}
                    value={storyLabel}
                    onChange={setStoryLabel}
                    onSubmit={submitStory}
                    onCancel={() => setCreatingStory(false)}
                    t={t}
                />
            )}
            <ul className={styles.treeRoot} role="tree">
                {tree.stories.map((story) => (
                    <StoryNode
                        story={story}
                        groups={(groupsByStory.get(story.id) || []).map((group) => ({
                            ...group,
                            fragmentIds: group.fragmentIds.map((id) => fragmentsById[id]).filter(Boolean),
                        }))}
                        groupOptions={allGroups}
                        key={story.id}
                        t={t}
                        onRename={onRenameStory}
                        onDelete={onDeleteStory}
                        onCreateGroup={onCreateGroup}
                        onRenameGroup={onRenameGroup}
                        onDeleteGroup={onDeleteGroup}
                        onMoveFragment={onMoveFragment}
                        onReorderFragment={onReorderFragment}
                        onSetFragmentDisposition={onSetFragmentDisposition}
                        onOpenDetails={onOpenDetails}
                        onDrop={handleDrop}
                    />
                ))}
            </ul>
            {unresolved.length > 0 && (
                <section className={styles.unresolved} data-testid="context-tree-unresolved">
                    <Group justify="space-between" mb="xs">
                        <div>
                            <Title className={styles.unresolvedTitle} order={5}>
                                {label(t, 'mod_archive.tree.unresolved_title', 'Unresolved fragments')}
                            </Title>
                            <Text className={styles.helperText} size="xs">
                                {label(t, 'mod_archive.tree.unresolved_desc', 'These fragments remain visible until a reviewer assigns a relationship.')}
                            </Text>
                        </div>
                        <Badge color="yellow">{unresolved.length}</Badge>
                    </Group>
                    <ul className={styles.fragmentList}>
                        {unresolved.map((fragment, index) => (
                            <FragmentNode
                                fragment={fragment}
                                groupId={null}
                                groupOptions={allGroups}
                                index={index}
                                groupLength={unresolved.length}
                                key={fragment.id}
                                t={t}
                                onMoveFragment={onMoveFragment}
                                onReorderFragment={onReorderFragment}
                                onSetFragmentDisposition={onSetFragmentDisposition}
                                onOpenDetails={onOpenDetails}
                                onDrop={handleDrop}
                            />
                        ))}
                    </ul>
                </section>
            )}
        </Paper>
    );
};

export default ContextArchiveTreeCanvas;
