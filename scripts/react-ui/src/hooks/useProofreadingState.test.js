import { renderHook, waitFor } from '@testing-library/react';
import useProofreadingState from './useProofreadingState';
import { vi, describe, it, expect } from 'vitest';

// Mock dependencies
vi.mock('react-router-dom', () => ({
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock('../utils/api', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: [] })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

vi.mock('@mantine/notifications', () => ({
    notifications: {
        show: vi.fn(),
    },
}));

describe('useProofreadingState', () => {
    it('initializes with default values', async () => {
        const { result } = renderHook(() => useProofreadingState());

        await waitFor(() => {
            expect(result.current.projects).toEqual([]);
        });

        expect(result.current.selectedProject).toBeNull();
        expect(result.current.originalContentStr).toBe('');
    });
});
