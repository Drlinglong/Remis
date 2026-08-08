import React, { useState } from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Badge, Button, Paper } from '@mantine/core';
import { IconGripVertical, IconTrash } from '@tabler/icons-react';

import styles from './PublishedContextWorkbench.module.css';
import { fragmentDropId, groupDropId } from './useFragmentDrag';

const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });

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
    onDeleteGroup,
    t,
}) => {
    const { setNodeRef, isOver } = useDroppable({
        id: groupDropId(group.id),
        data: { type: 'group', groupId: group.id },
    });
    const [confirmDelete, setConfirmDelete] = useState(false);

    return (
        <Paper
            ref={setNodeRef}
            className={`${styles.groupColumn} ${focused ? styles.focusedGroupColumn : ''}`}
            p="sm"
            withBorder
            data-remis-surface="paper"
            data-drag-over={isOver ? 'true' : 'false'}
            data-testid={`published-context-group-${group.id}`}
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
                            <Button size="compact-xs" color="red" onClick={() => onDeleteGroup(group.id)}>
                                {text(t, 'mod_archive.tree_v2.confirm_delete_group', 'Delete chain')}
                            </Button>
                            <Button size="compact-xs" variant="default" onClick={() => setConfirmDelete(false)}>
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

export default PublishedContextGroupColumn;
