import { useState } from 'react';
import { KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';

export const groupDropId = (groupId) => `group:${groupId}`;
export const fragmentDropId = (fragmentId) => `fragment:${fragmentId}`;

const fragmentIdFromDropId = (value) => String(value || '').replace(/^fragment:/, '');

export const getGroupForFragment = (groups, fragmentId) => groups.find((group) => (
    group.fragmentIds.includes(fragmentId)
));

export const resolveFragmentMove = ({ activeId, overId, groups }) => {
    const fragmentId = String(activeId || '');
    const dropId = String(overId || '');
    if (!fragmentId || !dropId) return null;

    const overFragmentId = dropId.startsWith('fragment:')
        ? fragmentIdFromDropId(dropId)
        : null;
    const targetGroupId = dropId.startsWith('group:')
        ? dropId.replace(/^group:/, '')
        : getGroupForFragment(groups, overFragmentId)?.id;
    const sourceGroupId = getGroupForFragment(groups, fragmentId)?.id;

    if (!targetGroupId || (overFragmentId === fragmentId && targetGroupId === sourceGroupId)) {
        return null;
    }
    return { fragmentId, targetGroupId, overFragmentId };
};

export const useFragmentDrag = ({ groups, onMoveFragment }) => {
    const [activeFragmentId, setActiveFragmentId] = useState(null);
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
        useSensor(KeyboardSensor),
    );

    const handleDragEnd = ({ active, over }) => {
        setActiveFragmentId(null);
        if (!over) return;
        const move = resolveFragmentMove({ activeId: active.id, overId: over.id, groups });
        if (move) onMoveFragment(move);
    };

    return {
        activeFragmentId,
        sensors,
        handleDragStart: ({ active }) => setActiveFragmentId(String(active.id)),
        handleDragCancel: () => setActiveFragmentId(null),
        handleDragEnd,
    };
};
