import { useEffect, useRef, useState } from 'react';

export const VIEW_EXIT_MS = 175;
export const VIEW_ENTER_MS = 250;

const emptySelection = { fragmentId: null, groupId: null };

const reducedMotionRequested = () => (
    typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
);

export const useContextWorkbenchSelection = ({ groups, fragments, identity }) => {
    const [selection, setSelection] = useState(emptySelection);
    const [transitionPhase, setTransitionPhase] = useState('idle');
    const timersRef = useRef([]);

    const clearTimers = () => {
        timersRef.current.forEach((timer) => window.clearTimeout(timer));
        timersRef.current = [];
    };

    const commitSelection = (nextSelection) => {
        setSelection(nextSelection);
        setTransitionPhase('idle');
    };

    const transitionTo = (nextSelection) => {
        const currentFocused = Boolean(selection.fragmentId || selection.groupId);
        const nextFocused = Boolean(nextSelection.fragmentId || nextSelection.groupId);
        clearTimers();

        if (currentFocused === nextFocused || reducedMotionRequested()) {
            commitSelection(nextSelection);
            return;
        }

        setTransitionPhase('exiting');
        timersRef.current.push(window.setTimeout(() => {
            setSelection(nextSelection);
            setTransitionPhase('entering');
            timersRef.current.push(window.setTimeout(() => {
                setTransitionPhase('idle');
                timersRef.current = [];
            }, VIEW_ENTER_MS));
        }, VIEW_EXIT_MS));
    };

    useEffect(() => () => clearTimers(), []);

    useEffect(() => {
        clearTimers();
        commitSelection(emptySelection);
    }, [identity]);

    useEffect(() => {
        if (selection.fragmentId && !fragments[selection.fragmentId]) {
            commitSelection(emptySelection);
            return;
        }
        if (selection.fragmentId) {
            const currentGroupId = groups.find((group) => (
                group.fragmentIds.includes(selection.fragmentId)
            ))?.id || null;
            if (selection.groupId !== currentGroupId) {
                commitSelection({ fragmentId: selection.fragmentId, groupId: currentGroupId });
                return;
            }
        }
        if (selection.groupId && !groups.some((group) => group.id === selection.groupId)) {
            commitSelection({ fragmentId: selection.fragmentId, groupId: null });
        }
    }, [fragments, groups, selection.fragmentId, selection.groupId]);

    const selectFragment = (fragmentId) => transitionTo({
        fragmentId,
        groupId: groups.find((group) => group.fragmentIds.includes(fragmentId))?.id || null,
    });

    const selectGroup = (groupId) => transitionTo({ fragmentId: null, groupId });

    return {
        selectedFragmentId: selection.fragmentId,
        selectedGroupId: selection.groupId,
        transitionPhase,
        selectFragment,
        selectGroup,
        clearSelection: () => transitionTo(emptySelection),
    };
};
