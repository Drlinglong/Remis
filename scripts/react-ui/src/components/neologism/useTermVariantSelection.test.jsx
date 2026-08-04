import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import { useTermVariantSelection } from './useTermVariantSelection';

vi.mock('../../utils/api', () => ({ default: { patch: vi.fn() } }));
vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }));

describe('useTermVariantSelection', () => {
    beforeEach(() => vi.clearAllMocks());

    it('persists a variant id and updates translation and explanation together', async () => {
        api.patch.mockResolvedValue({ data: { status: 'success' } });
        let candidates = [{ id: 'candidate-1', suggestion: 'First', reasoning: 'First reason' }];
        const setCandidates = (update) => { candidates = update(candidates); };
        const updateEditSuggestion = vi.fn();
        const setProcessing = vi.fn();
        const { result } = renderHook(() => useTermVariantSelection({
            candidate: candidates[0],
            projectId: 'project-1',
            setCandidates,
            setProcessing,
            updateEditSuggestion,
            t: (key) => key,
        }));

        await act(() => result.current({
            variant_id: 'variant-2',
            suggestion: 'Second',
            reasoning: 'Second reason',
        }));

        expect(api.patch).toHaveBeenCalledWith('/api/neologisms/candidate-1', {
            project_id: 'project-1',
            variant_id: 'variant-2',
        });
        expect(candidates[0]).toMatchObject({ suggestion: 'Second', reasoning: 'Second reason' });
        expect(updateEditSuggestion).toHaveBeenCalledWith('Second');
        expect(setProcessing).toHaveBeenNthCalledWith(1, true);
        expect(setProcessing).toHaveBeenLastCalledWith(false);
    });
});
