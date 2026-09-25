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

const sockets = [];

const deferred = () => {
    let resolve;
    const promise = new Promise((resolvePromise) => {
        resolve = resolvePromise;
    });
    return { promise, resolve };
};

class FakeWebSocket {
    constructor(url) {
        this.url = url;
        this.close = vi.fn();
        sockets.push(this);
    }
}

describe('useModArchiveAnalysis', () => {
    beforeEach(() => {
        sockets.length = 0;
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
            expect(api.get).toHaveBeenCalledWith(
                '/api/status/task-1',
                expect.objectContaining({ signal: expect.any(AbortSignal) }),
            );
        } finally {
            unmount();
            vi.useRealTimers();
        }
    });

    it('ignores files and status responses from the previously selected project', async () => {
        const projectAFiles = deferred();
        const projectAStatus = deferred();
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') return Promise.resolve({ data: [] });
            if (url === '/api/config') return Promise.resolve({ data: { api_providers: [] } });
            if (url === '/api/neologisms/mining-files/project-a') return projectAFiles.promise;
            if (url === '/api/neologisms/status/project-a') return projectAStatus.promise;
            if (url === '/api/neologisms/mining-files/project-b') {
                return Promise.resolve({ data: [{ file_path: 'b.yml' }] });
            }
            if (url === '/api/neologisms/status/project-b') {
                return Promise.resolve({ data: { status: 'idle', project_id: 'project-b' } });
            }
            throw new Error(`Unexpected GET ${url}`);
        });
        const { result, rerender } = renderHook(
            ({ projectId }) => useModArchiveAnalysis({
                selectedProject: projectId,
                onSelectedProjectChange: vi.fn(),
                onMiningComplete: vi.fn(),
                onMiningStatusChange: vi.fn(),
            }),
            { initialProps: { projectId: 'project-a' } },
        );

        rerender({ projectId: 'project-b' });
        await waitFor(() => expect(result.current.files).toEqual([{ file_path: 'b.yml' }]));
        expect(result.current.status?.status).toBe('idle');

        projectAFiles.resolve({ data: [{ file_path: 'a-late.yml' }] });
        projectAStatus.resolve({ data: { status: 'running', task_id: 'task-a' } });
        await act(async () => Promise.all([projectAFiles.promise, projectAStatus.promise]));

        expect(result.current.files).toEqual([{ file_path: 'b.yml' }]);
        expect(result.current.status?.status).toBe('idle');
        expect(sockets).toHaveLength(0);
    });

    it('ignores a late websocket message after switching projects', async () => {
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') return Promise.resolve({ data: [] });
            if (url === '/api/config') return Promise.resolve({ data: { api_providers: [] } });
            if (url.includes('/mining-files/')) return Promise.resolve({ data: [] });
            if (url === '/api/neologisms/status/project-a') {
                return Promise.resolve({ data: { status: 'running', task_id: 'task-a' } });
            }
            if (url === '/api/neologisms/status/project-b') {
                return Promise.resolve({ data: { status: 'idle', project_id: 'project-b' } });
            }
            throw new Error(`Unexpected GET ${url}`);
        });
        const onMiningComplete = vi.fn();
        const { result, rerender } = renderHook(
            ({ projectId }) => useModArchiveAnalysis({
                selectedProject: projectId,
                onSelectedProjectChange: vi.fn(),
                onMiningComplete,
                onMiningStatusChange: vi.fn(),
            }),
            { initialProps: { projectId: 'project-a' } },
        );

        await waitFor(() => expect(sockets).toHaveLength(1));
        const lateHandler = sockets[0].onmessage;
        rerender({ projectId: 'project-b' });
        await waitFor(() => expect(result.current.status?.status).toBe('idle'));

        act(() => {
            lateHandler({ data: JSON.stringify({ status: 'completed', task_id: 'task-a' }) });
        });
        expect(result.current.status?.status).toBe('idle');
        expect(onMiningComplete).not.toHaveBeenCalled();
    });

    it('does not let a late running poll regress a completed task', async () => {
        const latePoll = deferred();
        const onMiningComplete = vi.fn();
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') return Promise.resolve({ data: [{ project_id: 'project-1', source_language: 'en' }] });
            if (url === '/api/config') return Promise.resolve({ data: { api_providers: [{ value: 'local', available_models: ['model-1'] }] } });
            if (url.includes('/mining-files/')) return Promise.resolve({ data: [] });
            if (url.includes('/neologisms/status/')) return Promise.resolve({ data: { status: 'idle' } });
            if (url === '/api/status/task-1') return latePoll.promise;
            throw new Error(`Unexpected GET ${url}`);
        });
        const { result, unmount } = renderHook(() => useModArchiveAnalysis({
            selectedProject: 'project-1',
            onSelectedProjectChange: vi.fn(),
            onMiningComplete,
            onMiningStatusChange: vi.fn(),
        }));

        await waitFor(() => expect(result.current.status?.status).toBe('idle'));
        vi.useFakeTimers();
        try {
            await act(async () => result.current.startAnalysis());
            await act(async () => vi.advanceTimersByTimeAsync(1000));
            const socket = sockets.at(-1);
            act(() => {
                socket.onmessage({ data: JSON.stringify({ status: 'completed', task_id: 'task-1' }) });
            });
            expect(result.current.status?.status).toBe('completed');

            latePoll.resolve({ data: { status: 'running', task_id: 'task-1', progress: 25 } });
            await act(async () => latePoll.promise);
            expect(result.current.status?.status).toBe('completed');
            expect(onMiningComplete).toHaveBeenCalledTimes(1);
        } finally {
            unmount();
            vi.useRealTimers();
        }
    });

    it('aborts project-scoped requests on project switch and unmount', async () => {
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') return Promise.resolve({ data: [] });
            if (url === '/api/config') return Promise.resolve({ data: { api_providers: [] } });
            if (url.includes('/mining-files/')) return Promise.resolve({ data: [] });
            if (url.includes('/neologisms/status/')) return Promise.resolve({ data: { status: 'idle' } });
            throw new Error(`Unexpected GET ${url}`);
        });
        const { rerender, unmount } = renderHook(
            ({ projectId }) => useModArchiveAnalysis({
                selectedProject: projectId,
                onSelectedProjectChange: vi.fn(),
                onMiningComplete: vi.fn(),
                onMiningStatusChange: vi.fn(),
            }),
            { initialProps: { projectId: 'project-a' } },
        );

        await waitFor(() => expect(api.get).toHaveBeenCalledWith(
            '/api/neologisms/status/project-a',
            expect.objectContaining({ signal: expect.any(AbortSignal) }),
        ));
        const projectASignals = api.get.mock.calls
            .filter(([url]) => url.endsWith('/project-a'))
            .map(([, config]) => config.signal);

        rerender({ projectId: 'project-b' });
        expect(projectASignals.every((signal) => signal.aborted)).toBe(true);
        await waitFor(() => expect(api.get).toHaveBeenCalledWith(
            '/api/neologisms/status/project-b',
            expect.objectContaining({ signal: expect.any(AbortSignal) }),
        ));
        const projectBSignals = api.get.mock.calls
            .filter(([url]) => url.endsWith('/project-b'))
            .map(([, config]) => config.signal);

        unmount();
        expect(projectBSignals.every((signal) => signal.aborted)).toBe(true);
    });
});
