import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useTranslationRecovery } from './useTranslationRecovery';
import { useIncrementalCheckpointRecovery } from './useIncrementalCheckpointRecovery';

vi.mock('./useTranslationRecovery', () => ({
    useTranslationRecovery: vi.fn(),
}));

describe('useIncrementalCheckpointRecovery', () => {
    beforeEach(() => {
        useTranslationRecovery.mockReset();
        useTranslationRecovery.mockReturnValue({ canResume: false, recovery: null });
    });

    it('projects backend resumability into focused incremental UI state', async () => {
        const recovery = {
            task_id: 'task-213',
            checkpoint: { available: true, resumable: true },
            allowed_actions: ['resume_task'],
        };
        useTranslationRecovery.mockReturnValue({ canResume: true, recovery });
        const { result, rerender } = renderHook(
            ({ projectId }) => useIncrementalCheckpointRecovery(projectId),
            { initialProps: { projectId: 'project-213' } },
        );

        await waitFor(() => expect(result.current.checkpointFound).toBe(true));
        expect(result.current.checkpointInfo).toBe(recovery);

        act(() => result.current.setUseResume(true));
        expect(result.current.effectiveUseResume).toBe(true);

        useTranslationRecovery.mockReturnValue({ canResume: false, recovery: null });
        rerender({ projectId: 'project-213' });
        await waitFor(() => expect(result.current.checkpointFound).toBe(false));
        expect(result.current.checkpointInfo).toBeNull();
        expect(result.current.effectiveUseResume).toBe(false);
    });
});
