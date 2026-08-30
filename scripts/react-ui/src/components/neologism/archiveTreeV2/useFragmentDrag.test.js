import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { resolveFragmentMove, useFragmentDrag } from './useFragmentDrag';

const groups = [
    { id: 'group-1', fragmentIds: ['fragment-1', 'fragment-2'] },
    { id: 'group-2', fragmentIds: ['fragment-3'] },
];

describe('resolveFragmentMove', () => {
    it('moves a fragment to a group droppable', () => {
        expect(resolveFragmentMove({
            activeId: 'fragment-2',
            overId: 'group:group-2',
            groups,
        })).toEqual({
            fragmentId: 'fragment-2',
            targetGroupId: 'group-2',
            overFragmentId: null,
        });
    });

    it('reports a group rail drop without an insertion fragment', () => {
        const onMoveFragment = vi.fn();
        const { result } = renderHook(() => useFragmentDrag({ groups, onMoveFragment }));

        act(() => {
            result.current.handleDragEnd({
                active: { id: 'fragment-2' },
                over: { id: 'group:group-2' },
            });
        });

        expect(onMoveFragment).toHaveBeenCalledWith({
            fragmentId: 'fragment-2',
            targetGroupId: 'group-2',
            overFragmentId: null,
        });
    });

    it('preserves the insertion target for a fragment droppable', () => {
        expect(resolveFragmentMove({
            activeId: 'fragment-1',
            overId: 'fragment:fragment-3',
            groups,
        })).toEqual({
            fragmentId: 'fragment-1',
            targetGroupId: 'group-2',
            overFragmentId: 'fragment-3',
        });
    });

    it('ignores a no-op drop onto the active fragment', () => {
        expect(resolveFragmentMove({
            activeId: 'fragment-1',
            overId: 'fragment:fragment-1',
            groups,
        })).toBeNull();
    });
});
