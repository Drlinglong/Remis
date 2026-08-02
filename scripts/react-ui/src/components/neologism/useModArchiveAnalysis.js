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

const API_BASE_URL = '/api';
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '1453';
const STATUS_POLL_INTERVAL_MS = 1000;

export const TARGET_LANGUAGE_OPTIONS = [
    { value: 'zh-CN', label: 'Simplified Chinese (简体中文)' },
    { value: 'zh-TW', label: 'Traditional Chinese (繁體中文)' },
    { value: 'en', label: 'English' },
    { value: 'ja', label: 'Japanese (日本語)' },
    { value: 'ko', label: 'Korean (한국어)' },
    { value: 'fr', label: 'French (Français)' },
    { value: 'de', label: 'German (Deutsch)' },
    { value: 'ru', label: 'Russian (Русский)' },
    { value: 'es', label: 'Spanish (Español)' },
    { value: 'pt-BR', label: 'Portuguese (Português)' },
    { value: 'pl', label: 'Polish (Polski)' },
    { value: 'tr', label: 'Turkish (Türkçe)' },
];

const LANGUAGE_ALIASES = {
    english: 'en',
    l_english: 'en',
    chinese: 'zh-CN',
    simp_chinese: 'zh-CN',
    l_simp_chinese: 'zh-CN',
    zh: 'zh-CN',
    'zh-cn': 'zh-CN',
    zh_cn: 'zh-CN',
    pt: 'pt-BR',
    'pt-br': 'pt-BR',
    pt_br: 'pt-BR',
};

export const normalizeLanguageCode = (value) => {
    const normalized = (value || '').trim().toLowerCase();
    return LANGUAGE_ALIASES[normalized] || normalized;
};

const getSocketErrorStatus = (message) => normalizeAnalysisStatus({
    status: 'running',
    error: message,
});

export const useModArchiveAnalysis = ({
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
    const [upstreamVersion, setUpstreamVersion] = useState('');
    const [scanning, setScanning] = useState(false);
    const [status, setStatus] = useState(null);
    const [loadError, setLoadError] = useState(null);
    const [workflowError, setWorkflowError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const connectSocketRef = useRef(null);
    const terminalHandledRef = useRef(false);

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
            wsRef.current.onclose = null;
            wsRef.current.onerror = null;
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const applyStatus = useCallback((rawStatus, notifyComplete = true) => {
        const normalized = normalizeAnalysisStatus(rawStatus);
        setStatus(normalized);
        callbacksRef.current.onMiningStatusChange?.(normalized);
        if (!['completed', 'failed'].includes(normalized.status) || terminalHandledRef.current) return;
        terminalHandledRef.current = true;
        closeMiningSocket();
        if (normalized.status === 'completed' && notifyComplete) {
            callbacksRef.current.onMiningComplete?.(normalized);
        }
    }, [closeMiningSocket]);

    const updateStatusFromTask = useCallback((taskData) => {
        applyStatus(taskData);
    }, [applyStatus]);

    const connectMiningSocket = useCallback((taskId, attempt = 0) => {
        closeMiningSocket();
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const backendHost = `127.0.0.1:${BACKEND_PORT}`;
        const socket = new WebSocket(`${protocol}//${backendHost}/api/ws/status/${taskId}`);
        wsRef.current = socket;

        socket.onmessage = (event) => {
            try {
                updateStatusFromTask(JSON.parse(event.data));
            } catch (error) {
                console.error('Failed to parse Mod Archive status message', error);
                socket.close();
            }
        };
        socket.onerror = () => {
            setStatus((current) => {
                const next = getSocketErrorStatus(
                    translate('mod_archive.analysis.websocket_failed'),
                );
                const merged = { ...next, ...current, error: next.error };
                callbacksRef.current.onMiningStatusChange?.(merged);
                return merged;
            });
            socket.close();
        };
        socket.onclose = () => {
            if (wsRef.current === socket) wsRef.current = null;
            if (terminalHandledRef.current) return;
            const nextAttempt = attempt + 1;
            const delay = Math.min(1000 * (2 ** attempt), 5000);
            reconnectTimerRef.current = window.setTimeout(() => {
                connectSocketRef.current?.(taskId, nextAttempt);
            }, delay);
        };
    }, [closeMiningSocket, translate, updateStatusFromTask]);

    useEffect(() => {
        connectSocketRef.current = connectMiningSocket;
    }, [connectMiningSocket]);

    useEffect(() => {
        const taskId = status?.taskId;
        const isActive = ['starting', 'running', 'queued'].includes(status?.status);
        if (!taskId || !isActive) return undefined;

        let cancelled = false;
        const pollStatus = async () => {
            try {
                const response = await api.get(`${API_BASE_URL}/status/${encodeURIComponent(taskId)}`);
                if (!cancelled) applyStatus(response.data);
            } catch (error) {
                if (!cancelled) console.error('Failed to poll Mod Archive task status', error);
            }
        };
        const intervalId = window.setInterval(pollStatus, STATUS_POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            window.clearInterval(intervalId);
        };
    }, [applyStatus, status?.status, status?.taskId]);

    const fetchMiningStatus = useCallback(async (projectId) => {
        try {
            const response = await api.get(
                `${API_BASE_URL}/neologisms/status/${encodeURIComponent(projectId)}`,
            );
            applyStatus(response.data || { status: 'idle' }, false);
            const normalized = normalizeAnalysisStatus(response.data || { status: 'idle' });
            if (normalized.analysisScope) setAnalysisScope(normalized.analysisScope);
            if (['starting', 'running', 'queued'].includes(normalized.status) && normalized.taskId) {
                terminalHandledRef.current = false;
                connectSocketRef.current?.(normalized.taskId);
            }
        } catch (error) {
            console.error('Failed to restore Mod Archive status', error);
            setLoadError(translate('mod_archive.analysis.status_load_failed'));
        }
    }, [applyStatus, translate]);

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
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
            console.error('Failed to fetch Mod Archive projects', error);
            setLoadError(translate('mod_archive.analysis.projects_load_failed'));
        }
    }, [translate]);

    const fetchConfig = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/config`);
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
            console.error('Failed to fetch provider configuration', error);
            setLoadError(translate('mod_archive.analysis.config_load_failed'));
        }
    }, [translate]);

    const fetchFiles = useCallback(async (projectId) => {
        try {
            const response = await api.get(
                `${API_BASE_URL}/neologisms/mining-files/${encodeURIComponent(projectId)}`,
            );
            setFiles(normalizeArrayPayload(response.data, ['files', 'items', 'data', 'results']));
        } catch (error) {
            console.error('Failed to fetch Mod Archive source files', error);
            setLoadError(translate('mod_archive.analysis.files_load_failed'));
        }
    }, [translate]);

    useEffect(() => {
        fetchProjects();
        fetchConfig();
    }, [fetchConfig, fetchProjects]);

    useEffect(() => {
        terminalHandledRef.current = false;
        setWorkflowError(null);
        setLoadError(null);
        setSelectedFiles([]);
        setStatus(null);
        closeMiningSocket();
        if (selectedProject) {
            fetchFiles(selectedProject);
            fetchMiningStatus(selectedProject);
        } else {
            setFiles([]);
        }
    }, [closeMiningSocket, fetchFiles, fetchMiningStatus, selectedProject]);

    useEffect(() => () => closeMiningSocket(), [closeMiningSocket]);

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
            || ['starting', 'running', 'queued'].includes(status?.status)
        ) return;

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
            analysisScope,
            upstreamVersion,
        });
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/mine`, payload);
            const initialStatus = normalizeAnalysisStatus({
                status: 'running',
                task_id: response.data?.task_id,
                total_files: response.data?.total_files || selectedFiles.length || files.length,
                analysis_scope: analysisScope,
            });
            setStatus(initialStatus);
            callbacksRef.current.onMiningStatusChange?.(initialStatus);
            if (initialStatus.taskId) connectMiningSocket(initialStatus.taskId);
            notifications.show({
                title: translate('mod_archive.analysis.start_analysis'),
                message: translate('mod_archive.analysis.started_message'),
            });
        } catch (error) {
            const message = error?.response?.data?.detail || translate('mod_archive.analysis.start_failed');
            setWorkflowError(message);
            notifications.show({
                title: translate('neologism_review.common.error'),
                message,
            });
        } finally {
            setScanning(false);
        }
    }, [
        analysisScope,
        apiProvider,
        connectMiningSocket,
        currentProject?.sourceLanguage,
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
        analysisScope,
        setAnalysisScope,
        upstreamVersion,
        setUpstreamVersion,
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
