import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
    useContextWorkbenchSelection,
    VIEW_ENTER_MS,
    VIEW_EXIT_MS,
} from './useContextWorkbenchSelection';

const groups = [{ id: 'group-1', fragmentIds: ['fragment-1', 'fragment-2'] }];
const fragments = { 'fragment-1': { id: 'fragment-1' }, 'fragment-2': { id: 'fragment-2' } };

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
});

describe('useContextWorkbenchSelection', () => {
    it('stages overview and focused view changes around exit and entry motion', () => {
        vi.useFakeTimers();
        const { result } = renderHook(() => useContextWorkbenchSelection({ groups, fragments, identity: 'release-1' }));

        act(() => result.current.selectFragment('fragment-1'));
        expect(result.current.transitionPhase).toBe('exiting');
        expect(result.current.selectedFragmentId).toBeNull();

        act(() => vi.advanceTimersByTime(VIEW_EXIT_MS));
        expect(result.current.selectedFragmentId).toBe('fragment-1');
        expect(result.current.transitionPhase).toBe('entering');

        act(() => vi.advanceTimersByTime(VIEW_ENTER_MS));
        expect(result.current.transitionPhase).toBe('idle');
    });

    it('updates details immediately while remaining in the focused view', () => {
        vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: true });
        const { result } = renderHook(() => useContextWorkbenchSelection({ groups, fragments, identity: 'release-1' }));

        act(() => result.current.selectFragment('fragment-1'));
        act(() => result.current.selectFragment('fragment-2'));

        expect(result.current.selectedFragmentId).toBe('fragment-2');
        expect(result.current.transitionPhase).toBe('idle');
    });

    it('switches views instantly when reduced motion is requested', () => {
        vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: true });
        const { result } = renderHook(() => useContextWorkbenchSelection({ groups, fragments, identity: 'release-1' }));

        act(() => result.current.selectGroup('group-1'));

        expect(result.current.selectedGroupId).toBe('group-1');
        expect(result.current.transitionPhase).toBe('idle');
    });
});
