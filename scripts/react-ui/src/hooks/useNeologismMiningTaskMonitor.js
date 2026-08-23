import { useCallback, useEffect, useRef } from 'react';

import api from '../utils/api';

const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '1453';
const POLL_INTERVAL_MS = 1000;
const ACTIVE_STATUSES = new Set(['pending', 'starting', 'running', 'processing']);
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled', 'canceled']);

const isObjectRecord = (value) => value && typeof value === 'object' && !Array.isArray(value);
const firstDefined = (...values) => values.find(value => value !== undefined && value !== null);
const numberOrZero = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
};

const unwrapStatusPayload = (payload) => {
    let current = payload;
    for (let depth = 0; depth < 3; depth += 1) {
        if (!isObjectRecord(current)) return null;
        if (typeof current.status === 'string') return current;
        current = current.data || current.result;
    }
    return null;
};

export const normalizeNeologismMiningStatus = (payload, taskId = null) => {
    const taskData = unwrapStatusPayload(payload);
    if (!taskData) return null;

    const progress = isObjectRecord(taskData.progress) ? taskData.progress : {};
    const summary = isObjectRecord(taskData.summary) ? taskData.summary : {};
    const rawStatus = taskData.status;
    const status = rawStatus === 'processing' ? 'running' : rawStatus;

    return {
        status,
        processed_files: numberOrZero(firstDefined(taskData.processed_files, progress.current)),
        total_files: numberOrZero(firstDefined(taskData.total_files, progress.total)),
        new_terms: numberOrZero(firstDefined(taskData.new_terms, summary.new_terms)),
        duplicate_terms: numberOrZero(firstDefined(taskData.duplicate_terms, summary.duplicate_terms)),
        current_file: firstDefined(taskData.current_file, progress.current_file, null),
        error: firstDefined(taskData.error, summary.error, null),
        task_id: firstDefined(taskData.task_id, taskId, null),
    };
};

export function useNeologismMiningTaskMonitor({
    projectId,
    onStatus,
    onTerminal,
    onWebSocketError,
}) {
    const projectIdRef = useRef(projectId ? String(projectId) : null);
    const onStatusRef = useRef(onStatus);
    const onTerminalRef = useRef(onTerminal);
    const onWebSocketErrorRef = useRef(onWebSocketError);
    const socketRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const pollingTimerRef = useRef(null);
    const visibilityHandlerRef = useRef(null);
    const currentMonitorRef = useRef(null);
    const generationRef = useRef(0);
    const pollInFlightRef = useRef(null);
    const terminalTaskKeyRef = useRef(null);
    const connectSocketRef = useRef(null);

    projectIdRef.current = projectId ? String(projectId) : null;
    onStatusRef.current = onStatus;
    onTerminalRef.current = onTerminal;
    onWebSocketErrorRef.current = onWebSocketError;

    const isCurrentMonitor = useCallback((generation, currentProjectId) => (
        generationRef.current === generation
        && projectIdRef.current === currentProjectId
        && currentMonitorRef.current?.generation === generation
        && currentMonitorRef.current?.projectId === currentProjectId
    ), []);

    const clearReconnectTimer = useCallback(() => {
        if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }, []);

    const clearPollingTimer = useCallback(() => {
        if (pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
        }
    }, []);

    const removeVisibilityListener = useCallback(() => {
        if (visibilityHandlerRef.current && typeof document !== 'undefined') {
            document.removeEventListener('visibilitychange', visibilityHandlerRef.current);
        }
        visibilityHandlerRef.current = null;
    }, []);

    const closeSocket = useCallback(() => {
        const socket = socketRef.current;
        socketRef.current = null;
        if (!socket) return;
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
    }, []);

    const stopMonitoring = useCallback(() => {
        generationRef.current += 1;
        currentMonitorRef.current = null;
        pollInFlightRef.current = null;
        clearReconnectTimer();
        clearPollingTimer();
        removeVisibilityListener();
        closeSocket();
    }, [clearPollingTimer, clearReconnectTimer, closeSocket, removeVisibilityListener]);

    const notifyTerminal = useCallback((status, source, generation, currentProjectId) => {
        if (!isCurrentMonitor(generation, currentProjectId)) return;
        const taskKey = `${currentProjectId}:${status.task_id || currentMonitorRef.current?.taskId || 'unknown'}`;
        if (terminalTaskKeyRef.current === taskKey) return;
        terminalTaskKeyRef.current = taskKey;
        stopMonitoring();
        onTerminalRef.current?.(status, source);
    }, [isCurrentMonitor, stopMonitoring]);

    const handleStatus = useCallback((payload, source, generation, currentProjectId) => {
        if (!isCurrentMonitor(generation, currentProjectId)) return null;
        const taskId = currentMonitorRef.current?.taskId || null;
        const status = normalizeNeologismMiningStatus(payload, taskId);
        if (!status) return null;

        onStatusRef.current?.(status, source);
        if (TERMINAL_STATUSES.has(status.status)) {
            notifyTerminal(status, source, generation, currentProjectId);
        } else if (!ACTIVE_STATUSES.has(status.status)) {
            stopMonitoring();
        }
        return status;
    }, [isCurrentMonitor, notifyTerminal, stopMonitoring]);

    const pollStatus = useCallback(async (taskId, currentProjectId, generation) => {
        const monitor = currentMonitorRef.current;
        if (
            !isCurrentMonitor(generation, currentProjectId)
            || monitor?.taskId !== taskId
            || pollInFlightRef.current !== null
        ) return;

        pollInFlightRef.current = generation;
        try {
            const response = await api.get(
                `/api/neologisms/status/${encodeURIComponent(currentProjectId)}`,
            );
            if (!isCurrentMonitor(generation, currentProjectId)) return;
            handleStatus(response.data, 'polling', generation, currentProjectId);
        } catch (error) {
            if (isCurrentMonitor(generation, currentProjectId)) {
                console.error('Failed to poll neologism mining status', error);
            }
        } finally {
            if (pollInFlightRef.current === generation) pollInFlightRef.current = null;
        }
    }, [handleStatus, isCurrentMonitor]);

    const addVisibilityListener = useCallback((taskId, currentProjectId, generation) => {
        removeVisibilityListener();
        if (typeof document === 'undefined') return;

        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                void pollStatus(taskId, currentProjectId, generation);
            }
        };
        visibilityHandlerRef.current = handleVisibilityChange;
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }, [pollStatus, removeVisibilityListener]);

    const scheduleReconnect = useCallback((taskId, currentProjectId, generation, attempt) => {
        if (!taskId || !isCurrentMonitor(generation, currentProjectId)) return;
        clearReconnectTimer();
        const delay = Math.min(1000 * (2 ** attempt), 5000);
        reconnectTimerRef.current = window.setTimeout(() => {
            reconnectTimerRef.current = null;
            connectSocketRef.current?.(taskId, currentProjectId, generation, attempt + 1);
        }, delay);
    }, [clearReconnectTimer, isCurrentMonitor]);

    const connectSocket = useCallback((taskId, currentProjectId, generation, attempt = 0) => {
        if (!taskId || !isCurrentMonitor(generation, currentProjectId)) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const backendHost = `127.0.0.1:${BACKEND_PORT}`;
        let socket;
        try {
            socket = new WebSocket(
                `${protocol}//${backendHost}/api/ws/status/${encodeURIComponent(taskId)}`,
            );
        } catch (error) {
            console.error('Failed to connect neologism mining WebSocket', error);
            onWebSocketErrorRef.current?.();
            scheduleReconnect(taskId, currentProjectId, generation, attempt);
            return;
        }

        socketRef.current = socket;
        socket.onmessage = (event) => {
            if (!isCurrentMonitor(generation, currentProjectId) || socketRef.current !== socket) return;
            try {
                handleStatus(JSON.parse(event.data), 'websocket', generation, currentProjectId);
            } catch (error) {
                console.error('Failed to parse neologism mining WebSocket message', error);
                onWebSocketErrorRef.current?.();
                socket.close();
            }
        };
        socket.onerror = () => {
            if (!isCurrentMonitor(generation, currentProjectId) || socketRef.current !== socket) return;
            onWebSocketErrorRef.current?.();
            socket.close();
        };
        socket.onclose = () => {
            if (socketRef.current === socket) socketRef.current = null;
            if (isCurrentMonitor(generation, currentProjectId)) {
                scheduleReconnect(taskId, currentProjectId, generation, attempt);
            }
        };
    }, [handleStatus, isCurrentMonitor, scheduleReconnect]);

    connectSocketRef.current = connectSocket;

    const startMonitoring = useCallback((taskId, currentProjectId = projectIdRef.current) => {
        if (!currentProjectId) return;
        stopMonitoring();
        const normalizedProjectId = String(currentProjectId);
        const normalizedTaskId = taskId ? String(taskId) : null;
        const generation = generationRef.current;
        currentMonitorRef.current = {
            generation,
            projectId: normalizedProjectId,
            taskId: normalizedTaskId,
        };
        addVisibilityListener(normalizedTaskId, normalizedProjectId, generation);
        pollingTimerRef.current = window.setInterval(() => {
            void pollStatus(normalizedTaskId, normalizedProjectId, generation);
        }, POLL_INTERVAL_MS);
        if (normalizedTaskId) {
            connectSocket(normalizedTaskId, normalizedProjectId, generation);
        }
    }, [addVisibilityListener, connectSocket, pollStatus, stopMonitoring]);

    const restoreProject = useCallback(async (currentProjectId) => {
        if (!currentProjectId) return;
        const normalizedProjectId = String(currentProjectId);
        stopMonitoring();
        const generation = generationRef.current;
        currentMonitorRef.current = {
            generation,
            projectId: normalizedProjectId,
            taskId: null,
        };

        try {
            const response = await api.get(
                `/api/neologisms/status/${encodeURIComponent(normalizedProjectId)}`,
            );
            if (!isCurrentMonitor(generation, normalizedProjectId)) return;
            const status = handleStatus(response.data, 'polling', generation, normalizedProjectId);
            if (!status) {
                stopMonitoring();
                return;
            }
            if (!isCurrentMonitor(generation, normalizedProjectId)) return;
            if (ACTIVE_STATUSES.has(status.status)) {
                startMonitoring(status.task_id, normalizedProjectId);
            }
        } catch (error) {
            if (isCurrentMonitor(generation, normalizedProjectId)) {
                console.error('Failed to restore neologism mining status', error);
                stopMonitoring();
            }
        }
    }, [handleStatus, isCurrentMonitor, startMonitoring, stopMonitoring]);

    useEffect(() => {
        if (projectId) {
            void restoreProject(projectId);
        } else {
            stopMonitoring();
        }
        return stopMonitoring;
    }, [projectId, restoreProject, stopMonitoring]);

    const startMiningTask = useCallback((taskId) => {
        startMonitoring(taskId || null, projectIdRef.current);
    }, [startMonitoring]);

    return {
        startMiningTask,
        stopMonitoring,
    };
}
