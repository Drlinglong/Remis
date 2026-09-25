import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';

import api from '../../utils/api';
import { normalizeArrayPayload } from '../../utils/payload';
import {
    ANALYSIS_SCOPES,
    buildAnalysisPayload,
    normalizeAnalysisStatus,
} from './modArchiveModel';
import { normalizeLanguageCode, TARGET_LANGUAGE_OPTIONS } from './modArchiveLanguages';
export { TARGET_LANGUAGE_OPTIONS } from './modArchiveLanguages';
const API_BASE_URL = '/api';
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '1453';
const STATUS_POLL_INTERVAL_MS = 1000;
const ACTIVE_TASK_STATUSES = new Set(['starting', 'running', 'queued']);
const TERMINAL_TASK_STATUSES = new Set([
    'completed',
    'failed',
    'cancelled',
    'canceled',
    'interrupted',
    'partial_failed',
]);
const isAbortError = (error) => error?.name === 'AbortError' || error?.code === 'ERR_CANCELED';
const getSocketErrorStatus = (message) => normalizeAnalysisStatus({
    status: 'running',
    error: message,
});

export const useModArchiveAnalysis = ({
    allowArchiveAnalysis = true,
    selectedProject,
    onSelectedProjectChange,
    onMiningComplete,
    onMiningStatusChange,
}) => {
    const { t, i18n } = useTranslation();
    const translationRef = useRef(t);
    translationRef.current = t;
    const translate = useCallback((key, options) => translationRef.current(key, options), []);
    const callbacksRef = useRef({
        onSelectedProjectChange,
        onMiningComplete,
        onMiningStatusChange,
    });
    callbacksRef.current = {
        onSelectedProjectChange,
        onMiningComplete,
        onMiningStatusChange,
    };
    const selectedProjectRef = useRef(selectedProject);
    selectedProjectRef.current = selectedProject;
    const interfaceLanguage = normalizeLanguageCode(
        i18n?.resolvedLanguage || i18n?.language || 'en',
    );
    const [projects, setProjects] = useState([]);
    const [files, setFiles] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [providers, setProviders] = useState([]);
    const [apiProvider, setApiProvider] = useState('gemini');
    const [modelName, setModelName] = useState(null);
    const [targetLang, setTargetLang] = useState('zh-CN');
    const [descriptionLanguage, setDescriptionLanguage] = useState(interfaceLanguage);
    const [analysisScope, setAnalysisScope] = useState(ANALYSIS_SCOPES.TERMS_ONLY);
    const effectiveAnalysisScope = allowArchiveAnalysis
        ? analysisScope
        : ANALYSIS_SCOPES.TERMS_ONLY;
    const [upstreamVersion, setUpstreamVersion] = useState('');
    const [concurrencyLimit, setConcurrencyLimit] = useState('auto');
    const [scanning, setScanning] = useState(false);
    const [status, setStatus] = useState(null);
    const [loadError, setLoadError] = useState(null);
    const [workflowError, setWorkflowError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const connectSocketRef = useRef(null);
    const terminalHandledRef = useRef(false);
    const generationRef = useRef(0);
    const statusRef = useRef(null);

    useEffect(() => {
        const provider = providers.find((item) => item.value === apiProvider);
        setModelName(
            provider?.selected_model
            || provider?.default_model
            || provider?.available_models?.[0]
            || null,
        );
    }, [apiProvider, providers]);

    useEffect(() => {
        setDescriptionLanguage(interfaceLanguage);
    }, [interfaceLanguage]);

    const closeMiningSocket = useCallback(() => {
        if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.onmessage = null;
            wsRef.current.onclose = null;
            wsRef.current.onerror = null;
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const applyStatus = useCallback((rawStatus, {
        generation = generationRef.current,
        projectId = selectedProjectRef.current,
        taskId = null,
        notifyComplete = true,
    } = {}) => {
        if (
            generation !== generationRef.current
            || projectId !== selectedProjectRef.current
        ) return null;

        const normalizedStatus = normalizeAnalysisStatus(rawStatus);
        if (taskId && normalizedStatus.taskId && normalizedStatus.taskId !== taskId) return null;
        const normalized = normalizedStatus.taskId || !taskId
            ? normalizedStatus
            : { ...normalizedStatus, taskId };
        const current = statusRef.current;
        const sameTask = Boolean(
            current?.taskId
            && normalized.taskId
            && current.taskId === normalized.taskId
        );
        if (
            sameTask
            && TERMINAL_TASK_STATUSES.has(current.status)
            && !TERMINAL_TASK_STATUSES.has(normalized.status)
        ) return current;

        statusRef.current = normalized;
        setStatus(normalized);
        callbacksRef.current.onMiningStatusChange?.(normalized);
        if (!TERMINAL_TASK_STATUSES.has(normalized.status) || terminalHandledRef.current) {
            return normalized;
        }
        terminalHandledRef.current = true;
        closeMiningSocket();
        if (normalized.status === 'completed' && notifyComplete) {
            callbacksRef.current.onMiningComplete?.(normalized);
        }
        return normalized;
    }, [closeMiningSocket]);

    const connectMiningSocket = useCallback((
        taskId,
        attempt = 0,
        generation = generationRef.current,
        projectId = selectedProjectRef.current,
    ) => {
        if (
            generation !== generationRef.current
            || projectId !== selectedProjectRef.current
        ) return;
        closeMiningSocket();
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const backendHost = `127.0.0.1:${BACKEND_PORT}`;
        const socket = new WebSocket(`${protocol}//${backendHost}/api/ws/status/${taskId}`);
        wsRef.current = socket;

        socket.onmessage = (event) => {
            try {
                applyStatus(JSON.parse(event.data), { generation, projectId, taskId });
            } catch (error) {
                console.error('Failed to parse Mod Archive status message', error);
                socket.close();
            }
        };
        socket.onerror = () => {
            const next = getSocketErrorStatus(
                translate('mod_archive.analysis.websocket_failed'),
            );
            applyStatus(
                { ...next, ...statusRef.current, task_id: taskId, error: next.error },
                { generation, projectId, taskId },
            );
            socket.close();
        };
        socket.onclose = () => {
            if (wsRef.current === socket) wsRef.current = null;
            if (
                terminalHandledRef.current
                || generation !== generationRef.current
                || projectId !== selectedProjectRef.current
            ) return;
            const nextAttempt = attempt + 1;
            const delay = Math.min(1000 * (2 ** attempt), 5000);
            reconnectTimerRef.current = window.setTimeout(() => {
                connectSocketRef.current?.(taskId, nextAttempt, generation, projectId);
            }, delay);
        };
    }, [applyStatus, closeMiningSocket, translate]);

    useEffect(() => {
        connectSocketRef.current = connectMiningSocket;
    }, [connectMiningSocket]);

    useEffect(() => {
        const taskId = status?.taskId;
        const isActive = ACTIVE_TASK_STATUSES.has(status?.status);
        if (!taskId || !isActive) return undefined;

        const generation = generationRef.current;
        const projectId = selectedProjectRef.current;
        let cancelled = false;
        let inFlight = false;
        const controller = new AbortController();
        const pollStatus = async () => {
            if (inFlight) return;
            inFlight = true;
            try {
                const response = await api.get(
                    `${API_BASE_URL}/status/${encodeURIComponent(taskId)}`,
                    { signal: controller.signal },
                );
                if (!cancelled) {
                    applyStatus(response.data, { generation, projectId, taskId });
                }
            } catch (error) {
                if (!cancelled && !isAbortError(error)) {
                    console.error('Failed to poll Mod Archive task status', error);
                }
            } finally {
                inFlight = false;
            }
        };
        const intervalId = window.setInterval(pollStatus, STATUS_POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            controller.abort();
            window.clearInterval(intervalId);
        };
    }, [applyStatus, status?.status, status?.taskId]);

    const fetchMiningStatus = useCallback(async (projectId, { generation, signal } = {}) => {
        try {
            const response = await api.get(
                `${API_BASE_URL}/neologisms/status/${encodeURIComponent(projectId)}`,
                { signal },
            );
            const normalized = applyStatus(
                response.data || { status: 'idle' },
                { generation, projectId, notifyComplete: false },
            );
            if (!normalized) return;
            if (normalized.analysisScope && (
                allowArchiveAnalysis || normalized.analysisScope === ANALYSIS_SCOPES.TERMS_ONLY
            )) setAnalysisScope(normalized.analysisScope);
            if (ACTIVE_TASK_STATUSES.has(normalized.status) && normalized.taskId) {
                terminalHandledRef.current = false;
                connectSocketRef.current?.(normalized.taskId, 0, generation, projectId);
            }
        } catch (error) {
            if (isAbortError(error) || signal?.aborted) return;
            console.error('Failed to restore Mod Archive status', error);
            if (
                generation === generationRef.current
                && projectId === selectedProjectRef.current
            ) setLoadError(translate('mod_archive.analysis.status_load_failed'));
        }
    }, [allowArchiveAnalysis, applyStatus, translate]);

    const fetchProjects = useCallback(async ({ signal } = {}) => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`, { signal });
            if (signal?.aborted) return;
            const projectList = normalizeArrayPayload(
                response.data,
                ['projects', 'items', 'data', 'results'],
            );
            const options = projectList.map((project) => ({
                value: project.project_id,
                label: project.name || project.project_id,
                sourceLanguage: normalizeLanguageCode(project.source_language || 'en'),
            }));
            setProjects(options);
            if (!selectedProjectRef.current && options.length > 0) {
                callbacksRef.current.onSelectedProjectChange?.(options[0].value);
            }
        } catch (error) {
            if (isAbortError(error) || signal?.aborted) return;
            console.error('Failed to fetch Mod Archive projects', error);
            setLoadError(translate('mod_archive.analysis.projects_load_failed'));
        }
    }, [translate]);

    const fetchConfig = useCallback(async ({ signal } = {}) => {
        try {
            const response = await api.get(`${API_BASE_URL}/config`, { signal });
            if (signal?.aborted) return;
            const configuredProviders = normalizeArrayPayload(
                response.data,
                ['api_providers', 'providers', 'items', 'data', 'results'],
            );
            setProviders(configuredProviders);
            setApiProvider((current) => (
                configuredProviders.some((item) => item.value === current)
                    ? current
                    : configuredProviders[0]?.value || current
            ));
        } catch (error) {
            if (isAbortError(error) || signal?.aborted) return;
            console.error('Failed to fetch provider configuration', error);
            setLoadError(translate('mod_archive.analysis.config_load_failed'));
        }
    }, [translate]);

    const fetchFiles = useCallback(async (projectId, { generation, signal } = {}) => {
        try {
            const response = await api.get(
                `${API_BASE_URL}/neologisms/mining-files/${encodeURIComponent(projectId)}`,
                { signal },
            );
            if (
                signal?.aborted
                || generation !== generationRef.current
                || projectId !== selectedProjectRef.current
            ) return;
            setFiles(normalizeArrayPayload(response.data, ['files', 'items', 'data', 'results']));
        } catch (error) {
            if (isAbortError(error) || signal?.aborted) return;
            console.error('Failed to fetch Mod Archive source files', error);
            if (
                generation === generationRef.current
                && projectId === selectedProjectRef.current
            ) setLoadError(translate('mod_archive.analysis.files_load_failed'));
        }
    }, [translate]);

    useEffect(() => {
        const controller = new AbortController();
        fetchProjects({ signal: controller.signal });
        fetchConfig({ signal: controller.signal });
        return () => controller.abort();
    }, [fetchConfig, fetchProjects]);

    useEffect(() => {
        generationRef.current += 1;
        const generation = generationRef.current;
        const controller = new AbortController();
        terminalHandledRef.current = false;
        statusRef.current = null;
        setWorkflowError(null);
        setLoadError(null);
        setSelectedFiles([]);
        setStatus(null);
        setScanning(false);
        closeMiningSocket();
        if (selectedProject) {
            fetchFiles(selectedProject, { generation, signal: controller.signal });
            fetchMiningStatus(selectedProject, { generation, signal: controller.signal });
        } else {
            setFiles([]);
        }
        return () => controller.abort();
    }, [closeMiningSocket, fetchFiles, fetchMiningStatus, selectedProject]);

    useEffect(() => () => {
        generationRef.current += 1;
        statusRef.current = null;
        closeMiningSocket();
    }, [closeMiningSocket]);

    const currentProject = projects.find((project) => project.value === selectedProject);
    const availableTargetLanguages = useMemo(
        () => TARGET_LANGUAGE_OPTIONS.filter(
            (language) => normalizeLanguageCode(language.value) !== currentProject?.sourceLanguage,
        ),
        [currentProject?.sourceLanguage],
    );

    useEffect(() => {
        if (
            availableTargetLanguages.length > 0
            && !availableTargetLanguages.some((language) => language.value === targetLang)
        ) {
            setTargetLang(availableTargetLanguages[0].value);
        }
    }, [availableTargetLanguages, targetLang]);

    const startAnalysis = useCallback(async () => {
        if (
            !selectedProject
            || !apiProvider
            || !targetLang
            || normalizeLanguageCode(targetLang) === currentProject?.sourceLanguage
            || ACTIVE_TASK_STATUSES.has(status?.status)
        ) return;

        const generation = generationRef.current;
        const projectId = selectedProject;
        setScanning(true);
        setWorkflowError(null);
        terminalHandledRef.current = false;
        const payload = buildAnalysisPayload({
            selectedProject,
            apiProvider,
            modelName,
            targetLang,
            descriptionLanguage,
            selectedFiles,
            analysisScope: effectiveAnalysisScope,
            upstreamVersion,
            concurrencyLimit,
        });
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/mine`, payload);
            const initialStatus = normalizeAnalysisStatus({
                status: 'running',
                task_id: response.data?.task_id,
                total_files: response.data?.total_files || selectedFiles.length || files.length,
                analysis_scope: effectiveAnalysisScope,
            });
            if (
                generation !== generationRef.current
                || projectId !== selectedProjectRef.current
            ) return;
            statusRef.current = initialStatus;
            setStatus(initialStatus);
            callbacksRef.current.onMiningStatusChange?.(initialStatus);
            if (initialStatus.taskId) {
                connectMiningSocket(initialStatus.taskId, 0, generation, projectId);
            }
            notifications.show({
                title: translate('mod_archive.analysis.start_analysis'),
                message: translate('mod_archive.analysis.started_message'),
            });
        } catch (error) {
            if (
                generation !== generationRef.current
                || projectId !== selectedProjectRef.current
            ) return;
            const message = error?.response?.data?.detail || translate('mod_archive.analysis.start_failed');
            setWorkflowError(message);
            notifications.show({
                title: translate('neologism_review.common.error'),
                message,
            });
        } finally {
            if (
                generation === generationRef.current
                && projectId === selectedProjectRef.current
            ) setScanning(false);
        }
    }, [
        effectiveAnalysisScope,
        apiProvider,
        connectMiningSocket,
        currentProject?.sourceLanguage,
        concurrencyLimit,
        files.length,
        modelName,
        descriptionLanguage,
        selectedFiles,
        selectedProject,
        status?.status,
        translate,
        targetLang,
        upstreamVersion,
    ]);

    return {
        selectedProject,
        projects,
        files,
        selectedFiles,
        setSelectedFiles,
        providers,
        apiProvider,
        setApiProvider,
        modelName,
        setModelName,
        targetLang,
        setTargetLang,
        descriptionLanguage,
        setDescriptionLanguage,
        analysisScope: effectiveAnalysisScope,
        setAnalysisScope,
        upstreamVersion,
        setUpstreamVersion,
        concurrencyLimit,
        setConcurrencyLimit,
        scanning,
        status,
        loadError,
        workflowError,
        currentProject,
        availableTargetLanguages,
        startAnalysis,
        onSelectedProjectChange,
    };
};
