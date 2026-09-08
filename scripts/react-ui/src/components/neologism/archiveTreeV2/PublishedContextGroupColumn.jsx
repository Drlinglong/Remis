import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Badge, Paper } from '@mantine/core';
import { IconGripVertical } from '@tabler/icons-react';

import PublishedContextGroupHeading from './PublishedContextGroupHeading';
import styles from './PublishedContextWorkbench.module.css';
import { fragmentDropId, groupDropId } from './useFragmentDrag';

export const OVERVIEW_FRAGMENT_PREVIEW_LIMIT = 6;

const text = (t, key, fallback, options = {}) => {
    const value = t(key, { defaultValue: fallback, ...options });
    return typeof value === 'string'
        ? value.replace(/\{\{(\w+)\}\}/g, (_, name) => options[name] ?? `{{${name}}}`)
        : value;
};

const kickerFor = ({ focused, kind, t }) => {
    if (focused) return 'EVENT CHAIN';
    if (kind === 'needs-placement') {
        return text(t, 'mod_archive.tree_v2.needs_placement_label', 'UNPLACED');
    }
    if (kind === 'supporting') {
        return text(t, 'mod_archive.tree_v2.supporting_label', 'REFERENCE');
    }
    if (kind === 'archive') {
        return text(t, 'mod_archive.tree_v2.archive_only_label', 'ARCHIVE ONLY');
    }
    return 'CHAIN';
};

const FragmentCard = ({ fragment, index, selected, showSummary, onSelect }) => {
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
        >
            <IconGripVertical className={styles.dragHandle} size={15} aria-hidden="true" />
            <span className={styles.fragmentOrder}>{String(index + 1).padStart(2, '0')}</span>
            <span className={styles.fragmentBody}>
                <span className={styles.fragmentLabel}>{fragment.label}</span>
                {showSummary && <span className={styles.fragmentSummary}>{fragment.summary || '—'}</span>}
            </span>
            <Badge className={styles.fragmentCount} size="xs" variant="outline">{fragment.unitIds.length}</Badge>
        </button>
    );
};

const PublishedContextGroupColumn = ({
    group,
    fragments,
    selectedFragmentId,
    focused,
    onSelect,
    onSelectGroup,
    onRenameGroup,
    onDeleteGroup,
    kind = 'event',
    totalFragmentCount = fragments.length,
    totalUnitCount = null,
    onViewAll,
    isOverview = false,
    t,
}) => {
    const [expanded, setExpanded] = React.useState(false);
    const { setNodeRef, isOver } = useDroppable({
        id: groupDropId(group.id),
        data: { type: 'group', groupId: group.id },
    });
    const isPreview = isOverview && fragments.length > OVERVIEW_FRAGMENT_PREVIEW_LIMIT;
    const visibleFragments = isPreview && !expanded
        ? fragments.slice(0, OVERVIEW_FRAGMENT_PREVIEW_LIMIT)
        : fragments;
    const fragmentsId = `published-context-fragments-${group.id}`;
    const handleViewAll = (event) => {
        if (onViewAll) {
            onViewAll(group.id, event.currentTarget.id);
            return;
        }
        setExpanded((current) => !current);
    };
    const viewAllLabel = expanded && !onViewAll
        ? text(t, 'mod_archive.tree_v2.show_fewer_fragments', 'Show fewer items')
        : text(t, 'mod_archive.tree_v2.view_all_fragments', 'View all {{count}} items ({{remaining}} more)', {
            count: fragments.length,
            remaining: fragments.length - OVERVIEW_FRAGMENT_PREVIEW_LIMIT,
        });
    return (
        <Paper
            ref={setNodeRef}
            className={`${styles.groupColumn} ${focused ? styles.focusedGroupColumn : ''}`}
            p="sm"
            withBorder
            data-remis-surface="paper"
            data-drag-over={isOver ? 'true' : 'false'}
            data-group-kind={kind}
            data-testid={`published-context-group-${group.id}`}
        >
            <PublishedContextGroupHeading
                group={group}
                fragmentCount={isOverview && fragments.length === 1 && totalUnitCount !== null
                    ? totalUnitCount
                    : totalFragmentCount}
                focused={focused}
                showSummary={focused || (isOverview && fragments.length === 1)}
                kicker={kickerFor({ focused, kind, t })}
                onSelectGroup={onSelectGroup}
                onRenameGroup={onRenameGroup}
                onDeleteGroup={onDeleteGroup}
                t={t}
            />
            <div
                id={fragmentsId}
                data-testid={fragmentsId}
                className={`${styles.fragmentList} ${isOverview && fragments.length === 1 ? styles.overviewSingleFragmentList : ''} ${focused ? styles.focusedFragmentList : ''} ${expanded ? styles.expandedFragmentList : ''}`}
                data-preview-expanded={expanded ? 'true' : 'false'}
            >
                {visibleFragments.map((fragment, index) => (
                    <FragmentCard
                        key={fragment.id}
                        fragment={fragment}
                        index={index}
                        selected={fragment.id === selectedFragmentId}
                        showSummary={focused}
                        onSelect={onSelect}
                    />
                ))}
                {fragments.length === 0 && (
                    <div className={styles.dropHint} data-drag-over={isOver ? 'true' : 'false'}>
                        {text(t, 'mod_archive.tree_v2.empty_group', 'Drop the first card here.')}
                    </div>
                )}
            </div>
            {isPreview && (
                <button
                    id={`published-context-view-all-${group.id}`}
                    type="button"
                    className={styles.viewAllButton}
                    data-testid={`published-context-view-all-${group.id}`}
                    aria-controls={onViewAll ? 'published-context-detail' : fragmentsId}
                    aria-expanded={onViewAll ? undefined : String(expanded)}
                    onClick={handleViewAll}
                >
                    <span>{viewAllLabel}</span>
                    <span className={styles.viewAllHint} aria-hidden="true">
                        {onViewAll ? '→' : (expanded ? '↑' : '↓')}
                    </span>
                </button>
            )}
        </Paper>
    );
};

export default PublishedContextGroupColumn;
