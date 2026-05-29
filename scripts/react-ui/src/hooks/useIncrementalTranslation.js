import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import projectService from '../services/projectService';
import configService from '../services/configService';
import translationService from '../services/translationService';
import notificationService from '../services/notificationService';

const INCREMENTAL_STATE_STORAGE_KEY = 'incremental_translation_state_v1';
const LOCAL_PROVIDERS = ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];

const normalizeArrayPayload = (payload, keys = []) => {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];

    for (const key of keys) {
        if (Array.isArray(payload[key])) return payload[key];
    }

    return [];
};

export const useIncrementalTranslation = (notificationStyle) => {
    const { t } = useTranslation();
    const navigate = useNavigate();

    // UI Steps / Navigation
    const [active, setActive] = useState(0);
    const [loading, setLoading] = useState(false);
    const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);

    // Data State
    const [projects, setProjects] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [gameFilter, setGameFilter] = useState('all');
    const [selectedProject, setSelectedProject] = useState(null);
    const [apiProviders, setApiProviders] = useState([]);
    const [selectedProvider, setSelectedProvider] = useState('gemini');
    const [selectedModel, setSelectedModel] = useState('');
    const [models, setModels] = useState([]);
    const [customSourcePath, setCustomSourcePath] = useState('');
    const [selectedLangs, setSelectedLangs] = useState([]);
    const [batchSizeLimit, setBatchSizeLimit] = useState('');
    const [concurrencyLimit, setConcurrencyLimit] = useState('10');
    const [rpmLimit, setRpmLimit] = useState('40');

    // Validation / Scan Results
    const [archiveInfo, setArchiveInfo] = useState(null);
    const [scanResults, setScanResults] = useState(null);
    const [error, setError] = useState(null);
    const [errorKey, setErrorKey] = useState(null);

    // Execution State
    const [executing, setExecuting] = useState(false);
    const [progress, setProgress] = useState(0);
    const [progressInfo, setProgressInfo] = useState({});
    const [logs, setLogs] = useState([]);
    const [finalSummary, setFinalSummary] = useState(null);
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const [currentTaskMode, setCurrentTaskMode] = useState(null);
    
    // Checkpoints
    const [checkpointFound, setCheckpointFound] = useState(false);
    const [checkpointInfo, setCheckpointInfo] = useState(null);
    const [useResume, setUseResume] = useState(false);
    const [showResumeDetails, setShowResumeDetails] = useState(false);

    // Embedded Workshop
    const [embeddedWorkshopEnabled, setEmbeddedWorkshopEnabled] = useState(true);
    const [embeddedWorkshopFollowPrimary, setEmbeddedWorkshopFollowPrimary] = useState(true);
    const [embeddedWorkshopProvider, setEmbeddedWorkshopProvider] = useState('');
    const [embeddedWorkshopModel, setEmbeddedWorkshopModel] = useState('');
    const [embeddedWorkshopBatchSize, setEmbeddedWorkshopBatchSize] = useState('10');
    const [embeddedWorkshopConcurrency, setEmbeddedWorkshopConcurrency] = useState('1');
    const [embeddedWorkshopRpm, setEmbeddedWorkshopRpm] = useState('40');
    const [showWorkshopSettings, setShowWorkshopSettings] = useState(false);

    // Refs
    const wsRef = useRef(null);
    const pollTimerRef = useRef(null);
    const completionSourceRef = useRef(null);
    const preScanInFlightRef = useRef(false);
    const executionInFlightRef = useRef(false);
    const persistedStateRef = useRef(null);
    const restorationAppliedRef = useRef(false);
    const statusResyncRef = useRef(false);
    const routePrefillAppliedRef = useRef(false);
    const [projectsLoaded, setProjectsLoaded] = useState(false);
    const [configLoaded, setConfigLoaded] = useState(false);

    const getArchivedTargetLanguages = useCallback((info) => {
        if (!info) return [];
        if (Array.isArray(info.archived_languages)) {
            return info.archived_languages.filter(Boolean);
        }
        if (Array.isArray(info.target_languages)) {
            return info.target_languages.filter(Boolean);
        }
        return info.target_language ? [info.target_language] : [];
    }, []);

    const addLog = useCallback((msg) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    }, []);

    const clearTaskPolling = useCallback(() => {
        if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
        }
    }, []);

    const resolveProviderModels = useCallback((providerValue) => {
        const providerData = apiProviders.find((provider) => provider.value === providerValue);
        if (!providerData) return [];
        const availableModels = providerData.available_models || [];
        const customModels = providerData.custom_models || [];
        const merged = [...new Set([...availableModels, ...customModels])];
        if (providerData.selected_model && !merged.includes(providerData.selected_model)) {
            merged.unshift(providerData.selected_model);
        }
        if (providerData.default_model && !merged.includes(providerData.default_model)) {
            merged.unshift(providerData.default_model);
        }
        return merged;
    }, [apiProviders]);

    const applyProviderSelection = useCallback((providerValue, preferredModel = '', preferredConcurrency = null) => {
        const nextProvider = providerValue || 'gemini';
        const availableModels = resolveProviderModels(nextProvider);
        const nextModel = preferredModel && availableModels.includes(preferredModel)
            ? preferredModel
            : (availableModels[0] || '');

        setSelectedProvider(nextProvider);
        setModels(availableModels);
        setSelectedModel(nextModel);

        if (preferredConcurrency !== null && preferredConcurrency !== undefined) {
            setConcurrencyLimit(String(preferredConcurrency));
        } else {
            setConcurrencyLimit(LOCAL_PROVIDERS.includes(nextProvider) ? '1' : '10');
        }
    }, [resolveProviderModels]);

    const resetPersistedState = useCallback(() => {
        sessionStorage.removeItem(INCREMENTAL_STATE_STORAGE_KEY);
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        preScanInFlightRef.current = false;
        executionInFlightRef.current = false;
        completionSourceRef.current = null;
        statusResyncRef.current = false;
    }, []);

    const handleTaskUpdate = useCallback((data, isPreScan = false, source = 'unknown') => {
        if (!data) return;

        if (data.progress) {
            setProgress(data.progress.percent || 0);
            setProgressInfo(data.progress);
        }

        if (data.log) {
            setLogs(data.log);
        }

        if (data.status === 'completed') {
            completionSourceRef.current = source;
            console.info(`Incremental task completed via ${source}.`);
            clearTaskPolling();
            if (isPreScan) {
                preScanInFlightRef.current = false;
                setCurrentTaskId(null);
                setCurrentTaskMode(null);
                setScanResults({
                    ...(data.summary || {}),
                    file_summaries: data.file_summaries || [],
                    telemetry: data.telemetry || null,
                });
                setActive(2);
                setLoading(false);
            } else {
                executionInFlightRef.current = false;
                setFinalSummary(data);
                addLog(t('incremental_translation.translation_completed_success'));
                setProgress(100);
                setProgressInfo(data.progress || {});
                setExecuting(false);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        } else if (data.status === 'failed') {
            completionSourceRef.current = source;
            console.warn(`Incremental task failed via ${source}.`);
            clearTaskPolling();
            addLog(t('incremental_translation.task_failed_check_logs'));
            if (isPreScan) {
                preScanInFlightRef.current = false;
                setCurrentTaskId(null);
                setCurrentTaskMode(null);
                setLoading(false);
            } else {
                executionInFlightRef.current = false;
                setExecuting(false);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        }
    }, [clearTaskPolling, addLog, t]);

    const startTaskPolling = useCallback((taskId, isPreScan = false) => {
        clearTaskPolling();
        console.info(`Starting polling fallback for incremental task ${taskId}.`);
        pollTimerRef.current = setInterval(async () => {
            try {
                const res = await projectService.getTaskStatus(taskId);
                handleTaskUpdate(res.data, isPreScan, 'polling');
            } catch (err) {
                console.error('Polling task status failed:', err);
            }
        }, 1000);
    }, [clearTaskPolling, handleTaskUpdate]);

    const connectWebSocket = useCallback((taskId, isPreScan = false) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

        console.log(`Connecting to WS (${isPreScan ? 'Pre-scan' : 'Execution'}): ${wsUrl}`);
        if (wsRef.current) wsRef.current.close();
        startTaskPolling(taskId, isPreScan);
        
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.info(`Incremental task WebSocket connected: ${taskId}`);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleTaskUpdate(data, isPreScan, 'websocket');
        };

        ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            addLog(t('incremental_translation.status_ws_error'));
        };

        ws.onclose = () => {
            console.log('WebSocket connection closed.');
        };
    }, [startTaskPolling, handleTaskUpdate, addLog, t]);

    const checkCheckpoint = useCallback(async (project, sourcePath, targetLangs) => {
        try {
            const normalizedTargetLangs = Array.isArray(targetLangs) ? targetLangs.filter(Boolean) : [];
            if (normalizedTargetLangs.length === 0) {
                setCheckpointFound(false);
                setCheckpointInfo(null);
                return;
            }
            const modName = sourcePath.split(/[\\/]/).pop();
            const res = await translationService.getCheckpointStatus({
                project_id: project.project_id,
                mod_name: modName,
                target_lang_codes: normalizedTargetLangs,
            });
            if (res.data.exists && res.data.completed_count > 0) {
                setCheckpointFound(true);
                setCheckpointInfo(res.data);
                notificationService.info(t('incremental_translation.checkpoint_detected', { count: res.data.completed_count }), notificationStyle);
            } else {
                setCheckpointFound(false);
                setCheckpointInfo(null);
            }
        } catch (err) {
            console.error('Failed to check checkpoint status', err);
            setCheckpointInfo(null);
        }
    }, [notificationStyle, t]);

    const fetchProjects = useCallback(async () => {
        try {
            const response = await projectService.getActiveProjects();
            const projectList = normalizeArrayPayload(response.data, ['projects', 'items', 'data', 'results']);
            setProjects(projectList);
        } catch {
            notificationService.error(t('notification.error_generic'), notificationStyle);
        } finally {
            setProjectsLoaded(true);
        }
    }, [notificationStyle, t]);

    const fetchApiConfig = useCallback(async () => {
        try {
            const response = await configService.getConfig();
            const data = response.data;
            const providers = normalizeArrayPayload(data?.api_providers, ['items', 'data', 'results']);

            setApiProviders(providers);

            const defaultProvider = data.default_provider || 'gemini';
            setSelectedProvider(defaultProvider);

            const providerData = providers.find(p => p.value === defaultProvider);
            if (providerData) {
                const availableModels = providerData.available_models || providerData.custom_models || [];
                setModels(availableModels);
                setSelectedModel(data.default_model || availableModels[0] || '');
            }
            setBatchSizeLimit('');
            setRpmLimit(String(data.rpm_limit || 40));
        } catch (err) {
            console.error('Failed to fetch API config', err);
        } finally {
            setConfigLoaded(true);
        }
    }, []);

    const handleSelectProject = useCallback(async (project) => {
        setSelectedProject(project);
        setCustomSourcePath(project.source_path);
        setError(null);
        setArchiveInfo(null);
        setScanResults(null);
        setFinalSummary(null);
        setLogs([]);
        setErrorKey(null);
        setProgress(0);
        setProgressInfo({});
        setExecuting(false);
        setCheckpointFound(false);
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        completionSourceRef.current = null;
        statusResyncRef.current = false;
        setActive(1);

        try {
            setLoading(true);
            const res = await projectService.checkArchive(project.project_id);
            if (res.data.exists) {
                setArchiveInfo(res.data);
                const availableLangs = getArchivedTargetLanguages(res.data);
                setSelectedLangs(availableLangs);
                checkCheckpoint(project, project.source_path, availableLangs);
                if (availableLangs.length === 0) {
                    setErrorKey('incremental_translation.no_archived_target_languages');
                    setError(null);
                }
            } else {
                setErrorKey('incremental_translation.archive_missing');
                setError(null);
            }
        } catch {
            setErrorKey('incremental_translation.archive_missing');
            setError(null);
        } finally {
            setLoading(false);
        }
    }, [checkCheckpoint, getArchivedTargetLanguages]);

    const runPreScan = useCallback(async () => {
        if (!selectedProject || !customSourcePath || loading || executing || preScanInFlightRef.current || executionInFlightRef.current) return;
        const targetLangCodes = selectedLangs.length > 0 ? selectedLangs : getArchivedTargetLanguages(archiveInfo);
        if (targetLangCodes.length === 0) {
            notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
            return;
        }

        preScanInFlightRef.current = true;
        try {
            setLoading(true);
            setProgress(0);
            setProgressInfo({ percent: 0, stage_code: 'initializing', stage: t('incremental_translation.progress_stage_initializing') });
            setLogs([t('incremental_translation.pre_scan_bootstrap_log')]);
            const res = await translationService.startIncrementalUpdate(selectedProject.project_id, {
                project_id: selectedProject.project_id,
                target_lang_codes: targetLangCodes,
                dry_run: true,
                api_provider: selectedProvider,
                model: selectedModel,
                batch_size_limit: batchSizeLimit ? Number(batchSizeLimit) : null,
                concurrency_limit: Number(concurrencyLimit),
                rpm_limit: Number(rpmLimit),
                custom_source_path: customSourcePath,
                use_resume: useResume,
                embedded_workshop: {
                    enabled: embeddedWorkshopEnabled,
                    follow_primary_settings: embeddedWorkshopFollowPrimary,
                    api_provider: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopProvider,
                    api_model: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopModel,
                    batch_size_limit: Number(embeddedWorkshopBatchSize),
                    concurrency_limit: Number(embeddedWorkshopConcurrency),
                    rpm_limit: Number(embeddedWorkshopRpm),
                }
            });

            const taskId = res.data.task_id;
            if (taskId) {
                setCurrentTaskId(taskId);
                setCurrentTaskMode('pre_scan');
                connectWebSocket(taskId, true);
            } else {
                if (res.data.status === 'warning') {
                    notificationService.info(res.data.message || t('incremental_translation.no_files_warning'), notificationStyle);
                }
                setScanResults({
                    ...(res.data.summary || {}),
                    file_summaries: res.data.file_summaries || [],
                    telemetry: res.data.telemetry || null,
                });
                setActive(2);
                setLoading(false);
            }
        } catch (err) {
            console.error('Pre-scan error:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
            setLoading(false);
            preScanInFlightRef.current = false;
        }
    }, [
        selectedProject, customSourcePath, loading, executing, selectedLangs, archiveInfo, getArchivedTargetLanguages,
        selectedProvider, selectedModel, batchSizeLimit, concurrencyLimit, rpmLimit, useResume, embeddedWorkshopEnabled,
        embeddedWorkshopFollowPrimary, embeddedWorkshopProvider, embeddedWorkshopModel, embeddedWorkshopBatchSize,
        embeddedWorkshopConcurrency, embeddedWorkshopRpm, connectWebSocket, notificationStyle, t
    ]);

    const startTranslation = useCallback(async () => {
        if (loading || executing || preScanInFlightRef.current || executionInFlightRef.current) return;
        const targetLangCodes = selectedLangs.length > 0 ? selectedLangs : getArchivedTargetLanguages(archiveInfo);
        if (!selectedProject || targetLangCodes.length === 0) {
            notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
            return;
        }
        executionInFlightRef.current = true;
        setExecuting(true);
        setActive(3);
        setLogs([`[${new Date().toLocaleTimeString()}] ${t('incremental_translation.status_ws_initializing')}`]);
        setFinalSummary(null);
        setProgress(0);
        setProgressInfo({ percent: 0, stage_code: 'initializing', stage: t('incremental_translation.progress_stage_initializing') });
        completionSourceRef.current = null;

        try {
            const res = await translationService.startIncrementalUpdate(selectedProject.project_id, {
                project_id: selectedProject.project_id,
                target_lang_codes: targetLangCodes,
                dry_run: false,
                api_provider: selectedProvider,
                model: selectedModel,
                batch_size_limit: batchSizeLimit ? Number(batchSizeLimit) : null,
                concurrency_limit: Number(concurrencyLimit),
                rpm_limit: Number(rpmLimit),
                custom_source_path: customSourcePath,
                use_resume: useResume,
                embedded_workshop: {
                    enabled: embeddedWorkshopEnabled,
                    follow_primary_settings: embeddedWorkshopFollowPrimary,
                    api_provider: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopProvider,
                    api_model: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopModel,
                    batch_size_limit: Number(embeddedWorkshopBatchSize),
                    concurrency_limit: Number(embeddedWorkshopConcurrency),
                    rpm_limit: Number(embeddedWorkshopRpm),
                }
            });

            const taskId = res.data.task_id;
            if (!taskId) {
                throw new Error(t('incremental_translation.task_id_missing'));
            }

            setCurrentTaskId(taskId);
            setCurrentTaskMode('execution');
            connectWebSocket(taskId);

        } catch (err) {
            addLog(t('incremental_translation.critical_error', { message: err.message }));
            setExecuting(false);
            executionInFlightRef.current = false;
        }
    }, [
        loading, executing, selectedLangs, archiveInfo, getArchivedTargetLanguages, selectedProject,
        selectedProvider, selectedModel, batchSizeLimit, concurrencyLimit, rpmLimit, customSourcePath,
        useResume, embeddedWorkshopEnabled, embeddedWorkshopFollowPrimary, embeddedWorkshopProvider,
        embeddedWorkshopModel, embeddedWorkshopBatchSize, embeddedWorkshopConcurrency, embeddedWorkshopRpm,
        connectWebSocket, addLog, t
    ]);

    const openOutputFolder = useCallback(async () => {
        const folderPath = finalSummary?.output_dir;
        if (!folderPath) return;

        try {
            await translationService.openFolder(folderPath);
        } catch (err) {
            console.error('Failed to open incremental output folder:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    }, [finalSummary?.output_dir, notificationStyle, t]);

    // RESTORE STATE FROM SESSION STORAGE
    useEffect(() => {
        if (restorationAppliedRef.current || !projectsLoaded || !configLoaded) return;

        const persistedState = persistedStateRef.current;
        if (!persistedState) {
            restorationAppliedRef.current = true;
            return;
        }

        const matchedProject = persistedState.selectedProject?.project_id
            ? projects.find((project) => project.project_id === persistedState.selectedProject.project_id) || persistedState.selectedProject
            : null;

        if (matchedProject) setSelectedProject(matchedProject);
        if (typeof persistedState.active === 'number') setActive(persistedState.active);
        if (typeof persistedState.loading === 'boolean') setLoading(persistedState.loading);
        if (persistedState.customSourcePath) setCustomSourcePath(persistedState.customSourcePath);
        if (Array.isArray(persistedState.selectedLangs)) setSelectedLangs(persistedState.selectedLangs);
        if (persistedState.archiveInfo) setArchiveInfo(persistedState.archiveInfo);
        if (persistedState.scanResults) setScanResults(persistedState.scanResults);
        if (persistedState.errorKey) setErrorKey(persistedState.errorKey);
        if (typeof persistedState.executing === 'boolean') setExecuting(persistedState.executing);
        if (typeof persistedState.progress === 'number') setProgress(persistedState.progress);
        if (persistedState.progressInfo) setProgressInfo(persistedState.progressInfo);
        if (Array.isArray(persistedState.logs)) setLogs(persistedState.logs);
        if (persistedState.finalSummary) setFinalSummary(persistedState.finalSummary);
        if (typeof persistedState.checkpointFound === 'boolean') setCheckpointFound(persistedState.checkpointFound);
        if (persistedState.checkpointInfo) setCheckpointInfo(persistedState.checkpointInfo);
        if (typeof persistedState.useResume === 'boolean') setUseResume(persistedState.useResume);
        if (typeof persistedState.showResumeDetails === 'boolean') setShowResumeDetails(persistedState.showResumeDetails);
        if (typeof persistedState.embeddedWorkshopEnabled === 'boolean') setEmbeddedWorkshopEnabled(persistedState.embeddedWorkshopEnabled);
        if (typeof persistedState.embeddedWorkshopFollowPrimary === 'boolean') setEmbeddedWorkshopFollowPrimary(persistedState.embeddedWorkshopFollowPrimary);
        if (persistedState.embeddedWorkshopProvider) setEmbeddedWorkshopProvider(persistedState.embeddedWorkshopProvider);
        if (persistedState.embeddedWorkshopModel) setEmbeddedWorkshopModel(persistedState.embeddedWorkshopModel);
        if (persistedState.embeddedWorkshopBatchSize) setEmbeddedWorkshopBatchSize(String(persistedState.embeddedWorkshopBatchSize));
        if (persistedState.embeddedWorkshopConcurrency) setEmbeddedWorkshopConcurrency(String(persistedState.embeddedWorkshopConcurrency));
        if (persistedState.embeddedWorkshopRpm) setEmbeddedWorkshopRpm(String(persistedState.embeddedWorkshopRpm));
        if (typeof persistedState.showWorkshopSettings === 'boolean') setShowWorkshopSettings(persistedState.showWorkshopSettings);
        if (persistedState.currentTaskId) setCurrentTaskId(persistedState.currentTaskId);
        if (persistedState.currentTaskMode) setCurrentTaskMode(persistedState.currentTaskMode);
        if (persistedState.completionSource) completionSourceRef.current = persistedState.completionSource;

        applyProviderSelection(
            persistedState.selectedProvider || 'gemini',
            persistedState.selectedModel || '',
            persistedState.concurrencyLimit ?? null,
        );
        if (persistedState.batchSizeLimit !== undefined && persistedState.batchSizeLimit !== null) {
            setBatchSizeLimit(String(persistedState.batchSizeLimit));
        }
        if (persistedState.rpmLimit) setRpmLimit(String(persistedState.rpmLimit));

        restorationAppliedRef.current = true;
    }, [configLoaded, projects, projectsLoaded, applyProviderSelection]);

    // SYNC STATE TO SESSION STORAGE
    useEffect(() => {
        if (!restorationAppliedRef.current) return;

        const stateToPersist = {
            active,
            loading,
            selectedProject,
            selectedProvider,
            selectedModel,
            customSourcePath,
            selectedLangs,
            batchSizeLimit,
            concurrencyLimit,
            rpmLimit,
            archiveInfo,
            scanResults,
            errorKey,
            executing,
            progress,
            progressInfo,
            logs,
            finalSummary,
            checkpointFound,
            checkpointInfo,
            useResume,
            showResumeDetails,
            embeddedWorkshopEnabled,
            embeddedWorkshopFollowPrimary,
            embeddedWorkshopProvider,
            embeddedWorkshopModel,
            embeddedWorkshopBatchSize,
            embeddedWorkshopConcurrency,
            embeddedWorkshopRpm,
            showWorkshopSettings,
            currentTaskId,
            currentTaskMode,
            completionSource: completionSourceRef.current,
        };

        try {
            sessionStorage.setItem(INCREMENTAL_STATE_STORAGE_KEY, JSON.stringify(stateToPersist));
        } catch (err) {
            console.warn('Failed to persist incremental translation state:', err);
        }
    }, [
        active, archiveInfo, checkpointFound, checkpointInfo, batchSizeLimit, concurrencyLimit, currentTaskId,
        currentTaskMode, customSourcePath, embeddedWorkshopBatchSize, embeddedWorkshopConcurrency,
        embeddedWorkshopEnabled, embeddedWorkshopFollowPrimary, embeddedWorkshopModel, embeddedWorkshopProvider,
        embeddedWorkshopRpm, executing, finalSummary, loading, logs, progress, progressInfo, rpmLimit, scanResults,
        selectedLangs, selectedModel, selectedProject, selectedProvider, showResumeDetails, showWorkshopSettings,
        useResume
    ]);

    // LOAD BASICS ON MOUNT
    useEffect(() => {
        try {
            const rawState = sessionStorage.getItem(INCREMENTAL_STATE_STORAGE_KEY);
            persistedStateRef.current = rawState ? JSON.parse(rawState) : null;
        } catch (err) {
            console.warn('Failed to read incremental translation persisted state:', err);
            persistedStateRef.current = null;
        }
        fetchProjects();
        fetchApiConfig();
    }, [fetchProjects, fetchApiConfig]);

    // SYNC WORKSHOP CONFIG WITH PRIMARY IF NECESSARY
    useEffect(() => {
        if (embeddedWorkshopFollowPrimary) {
            return;
        }

        const modelsForProvider = resolveProviderModels(embeddedWorkshopProvider);
        if (!embeddedWorkshopProvider && apiProviders.length > 0) {
            const providerValue = apiProviders[0]?.value || '';
            setEmbeddedWorkshopProvider(providerValue);
            setEmbeddedWorkshopModel(resolveProviderModels(providerValue)[0] || '');
            return;
        }

        if (modelsForProvider.length > 0 && !modelsForProvider.includes(embeddedWorkshopModel)) {
            setEmbeddedWorkshopModel(modelsForProvider[0]);
        }
    }, [
        apiProviders, embeddedWorkshopFollowPrimary, embeddedWorkshopModel, embeddedWorkshopProvider, resolveProviderModels
    ]);

    // RESYNC ONGOING TASK IF RESTORED ACTIVE WORK
    useEffect(() => {
        if (!restorationAppliedRef.current || statusResyncRef.current || !currentTaskId || !currentTaskMode) return;
        if (!loading && !executing) return;

        statusResyncRef.current = true;

        const isPreScan = currentTaskMode === 'pre_scan';
        projectService.getTaskStatus(currentTaskId)
            .then((res) => {
                const taskStatus = res.data?.status;
                if (taskStatus === 'completed' || taskStatus === 'failed') {
                    handleTaskUpdate(res.data, isPreScan, 'polling');
                    return;
                }
                connectWebSocket(currentTaskId, isPreScan);
            })
            .catch((resumeErr) => {
                console.error('Failed to resume incremental task state:', resumeErr);
                connectWebSocket(currentTaskId, isPreScan);
            });
    }, [currentTaskId, currentTaskMode, executing, loading, handleTaskUpdate, connectWebSocket]);

    // CLEANUP ON UNMOUNT
    useEffect(() => {
        return () => {
            clearTaskPolling();
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [clearTaskPolling]);

    return {
        active, setActive,
        loading, setLoading,
        showTutorialPrompt, setShowTutorialPrompt,
        projects, searchQuery, setSearchQuery,
        gameFilter, setGameFilter,
        selectedProject, handleSelectProject,
        apiProviders, selectedProvider, handleProviderChange: applyProviderSelection,
        selectedModel, setSelectedModel,
        models, customSourcePath, setCustomSourcePath,
        selectedLangs, setSelectedLangs,
        batchSizeLimit, setBatchSizeLimit,
        concurrencyLimit, setConcurrencyLimit,
        rpmLimit, setRpmLimit,
        archiveInfo, scanResults, error, errorKey,setErrorKey,
        executing, progress, progressInfo, logs, finalSummary,
        checkpointFound, checkpointInfo, useResume, setUseResume,
        showResumeDetails, setShowResumeDetails,
        embeddedWorkshopEnabled, setEmbeddedWorkshopEnabled,
        embeddedWorkshopFollowPrimary, setEmbeddedWorkshopFollowPrimary,
        embeddedWorkshopProvider, setEmbeddedWorkshopProvider,
        embeddedWorkshopModel, setEmbeddedWorkshopModel,
        embeddedWorkshopBatchSize, setEmbeddedWorkshopBatchSize,
        embeddedWorkshopConcurrency, setEmbeddedWorkshopConcurrency,
        embeddedWorkshopRpm, setEmbeddedWorkshopRpm,
        showWorkshopSettings, setShowWorkshopSettings,
        runPreScan, startTranslation, openOutputFolder,
        resetPersistedState, addLog, getArchivedTargetLanguages
    };
};

export default useIncrementalTranslation;
