import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import { ANALYSIS_SCOPES } from './modArchiveModel';
import { useModArchiveAnalysis } from './useModArchiveAnalysis';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key) => key,
        i18n: { language: 'zh-CN', resolvedLanguage: 'zh-CN' },
    }),
}));

vi.mock('@mantine/notifications', () => ({
    notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
    default: { get: vi.fn(), post: vi.fn() },
}));

class FakeWebSocket {
    constructor() {
        this.close = vi.fn();
    }
}

describe('useModArchiveAnalysis', () => {
    beforeEach(() => {
        global.WebSocket = FakeWebSocket;
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') {
                return Promise.resolve({ data: [{ project_id: 'project-1', name: 'Demo', source_language: 'en' }] });
            }
            if (url === '/api/config') {
                return Promise.resolve({ data: { api_providers: [{ value: 'local', available_models: ['model-1'] }] } });
            }
            if (url === '/api/neologisms/mining-files/project-1') {
                return Promise.resolve({ data: [{ file_path: 'events.yml' }] });
            }
            if (url === '/api/neologisms/status/project-1') {
                return Promise.resolve({ data: { status: 'idle' } });
            }
            if (url === '/api/status/task-1') {
                return Promise.resolve({ data: {
                    status: 'running',
                    task_id: 'task-1',
                    progress: {
                        current: 4,
                        total: 6,
                        current_batch: 4,
                        total_batches: 6,
                        percent: 16,
                    },
                } });
            }
            throw new Error(`Unexpected GET ${url}`);
        });
        api.post.mockResolvedValue({ data: { task_id: 'task-1', total_files: 1 } });
    });

    it('sends the selected scope through the maintained analysis workflow', async () => {
        const { result } = renderHook(() => useModArchiveAnalysis({
            selectedProject: 'project-1',
            onSelectedProjectChange: vi.fn(),
            onMiningComplete: vi.fn(),
            onMiningStatusChange: vi.fn(),
        }));

        await waitFor(() => expect(result.current.status?.status).toBe('idle'));
        act(() => {
            result.current.setAnalysisScope(ANALYSIS_SCOPES.NARRATIVE_CONTEXT);
            result.current.setUpstreamVersion('  2.0  ');
            result.current.setConcurrencyLimit('5');
        });
        await act(async () => {
            await result.current.startAnalysis();
        });

        expect(api.post).toHaveBeenCalledWith('/api/neologisms/mine', expect.objectContaining({
            project_id: 'project-1',
            analysis_scope: 'narrative_context',
            upstream_version: '2.0',
            concurrency_limit: 5,
        }));
    });

    it('polls persisted task progress when websocket pushes are quiet', async () => {
        const { result, unmount } = renderHook(() => useModArchiveAnalysis({
            selectedProject: 'project-1',
            onSelectedProjectChange: vi.fn(),
            onMiningComplete: vi.fn(),
            onMiningStatusChange: vi.fn(),
        }));

        await waitFor(() => expect(result.current.status?.status).toBe('idle'));
        vi.useFakeTimers();
        try {
            await act(async () => {
                await result.current.startAnalysis();
            });
            await act(async () => {
                await vi.advanceTimersByTimeAsync(1000);
            });
            expect(result.current.status).toMatchObject({
                currentBatch: 4,
                totalBatches: 6,
                overallPercent: 16,
            });
            expect(api.get).toHaveBeenCalledWith('/api/status/task-1');
        } finally {
            unmount();
            vi.useRealTimers();
        }
    });
});
