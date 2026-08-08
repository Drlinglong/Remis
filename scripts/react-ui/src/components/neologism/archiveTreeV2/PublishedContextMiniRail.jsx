import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Badge } from '@mantine/core';

import styles from './PublishedContextWorkbench.module.css';
import { groupDropId } from './useFragmentDrag';

const PublishedContextMiniRail = ({ group, fragmentCount, onSelectGroup }) => {
    const dropId = groupDropId(group.id);
    const { setNodeRef, isOver } = useDroppable({
        id: dropId,
        data: { type: 'group', groupId: group.id },
    });

    return (
        <button
            ref={setNodeRef}
            type="button"
            className={styles.miniRail}
            data-drag-over={isOver ? 'true' : 'false'}
            data-drop-target={dropId}
            data-testid={`published-context-mini-rail-${group.id}`}
            title={group.label}
            onClick={() => onSelectGroup(group.id)}
        >
            <span className={styles.miniRailLabel}>{group.label}</span>
            <Badge className={styles.miniRailCount} size="xs" variant="outline">{fragmentCount}</Badge>
        </button>
    );
};

export default PublishedContextMiniRail;
