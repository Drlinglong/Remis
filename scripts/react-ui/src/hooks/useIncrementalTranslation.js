import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import projectService from '../services/projectService';
import configService from '../services/configService';
import translationService from '../services/translationService';
import notificationService from '../services/notificationService';
import { open } from '@tauri-apps/plugin-dialog';
import {
    buildIncrementalUpdatePayload,
    getArchivedTargetLanguages,
    INCREMENTAL_STATE_STORAGE_KEY,
    normalizeArrayPayload,
} from './incrementalTranslationPayload';
import {
    applyIncrementalStateSnapshot,
    buildIncrementalStateSnapshot,
    readIncrementalStateSnapshot,
    resolveInFlightIncrementalTaskId,
    writeIncrementalStateSnapshot,
} from './incrementalTranslationPersistence';
import {
    buildProviderSelection,
    buildEmbeddedWorkshopSelection,
} from './incrementalTranslationProviders';
import { requestIncrementalCheckpointStatus } from './incrementalTranslationCheckpoint';
import {
    resyncIncrementalTask,
    shouldResyncIncrementalTask,
} from './incrementalTranslationTaskResync';
import { useIncrementalTaskMonitor } from './useIncrementalTaskMonitor';

export const useIncrementalTranslation = (notificationStyle) => {
    const { t } = useTranslation();
    const location = useLocation();

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
    const [conflictingTaskId, setConflictingTaskId] = useState(null);
    
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
    const preScanInFlightRef = useRef(false);
    const executionInFlightRef = useRef(false);
    const persistedStateRef = useRef(null);
    const restorationAppliedRef = useRef(false);
    const statusResyncRef = useRef(false);
    const routeSelectionAppliedRef = useRef(false);
    const [projectsLoaded, setProjectsLoaded] = useState(false);
    const [configLoaded, setConfigLoaded] = useState(false);

    const addLog = useCallback((msg) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    }, []);

    const {
        completionSourceRef,
        connectWebSocket,
        handleTaskUpdate,
    } = useIncrementalTaskMonitor({
        addLog,
        executionInFlightRef,
        preScanInFlightRef,
        setActive,
        setConflictingTaskId,
        setCurrentTaskId,
        setCurrentTaskMode,
        setExecuting,
        setFinalSummary,
        setLoading,
        setLogs,
        setProgress,
        setProgressInfo,
        setScanResults,
        t,
    });

    const applyProviderSelection = useCallback((providerValue, preferredModel = '', preferredConcurrency = null) => {
        const selection = buildProviderSelection({
            providers: apiProviders,
            providerValue,
            preferredModel,
            preferredConcurrency,
        });

        setSelectedProvider(selection.selectedProvider);
        setModels(selection.models);
        setSelectedModel(selection.selectedModel);
        setConcurrencyLimit(selection.concurrencyLimit);
    }, [apiProviders]);

    const resetPersistedState = useCallback(() => {
        sessionStorage.removeItem(INCREMENTAL_STATE_STORAGE_KEY);
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        setConflictingTaskId(null);
        preScanInFlightRef.current = false;
        executionInFlightRef.current = false;
        completionSourceRef.current = null;
        statusResyncRef.current = false;
    }, [completionSourceRef]);

    const checkCheckpoint = useCallback(async (project, sourcePath, targetLangs) => {
        try {
            const checkpoint = await requestIncrementalCheckpointStatus({
                project,
                sourcePath,
                targetLangs,
                translationService,
            });
            if (checkpoint.found) {
                setCheckpointFound(true);
                setCheckpointInfo(checkpoint.info);
                notificationService.info(t('incremental_translation.checkpoint_detected', { count: checkpoint.info.completed_count }), notificationStyle);
            } else {
                setCheckpointFound(false);
                setCheckpointInfo(null);
            }
        } catch (err) {
            console.error('Failed to check checkpoint status', err);
            setCheckpointInfo(null);
        }
    }, [notificationStyle, t]);

    const handleSelectFolder = useCallback(async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: t('incremental_translation.select_new_folder')
            });
            if (selected && typeof selected === 'string') {
                setCustomSourcePath(selected);
                if (selectedProject) {
                    checkCheckpoint(selectedProject, selected, selectedLangs);
                }
            }
        } catch (err) {
            console.error('Failed to open folder dialog:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    }, [checkCheckpoint, notificationStyle, selectedLangs, selectedProject, t]);

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

            const selection = buildProviderSelection({
                providers,
                providerValue: data.default_provider || 'gemini',
                preferredModel: data.default_model || '',
            });
            setSelectedProvider(selection.selectedProvider);
            setModels(selection.models);
            setSelectedModel(selection.selectedModel);
            setConcurrencyLimit(selection.concurrencyLimit);
            setBatchSizeLimit('');
            setRpmLimit(String(data.rpm_limit || 40));
        } catch (err) {
            console.error('Failed to fetch API config', err);
        } finally {
            setConfigLoaded(true);
        }
    }, []);

    const handleSelectProject = useCallback(async (project, sourcePathOverride = null) => {
        const inFlightTaskId = resolveInFlightIncrementalTaskId({
            currentTaskId,
            executionInFlight: executionInFlightRef.current,
            preScanInFlight: preScanInFlightRef.current,
        });
        const nextSourcePath = sourcePathOverride || project.source_path;
        setSelectedProject(project);
        setCustomSourcePath(nextSourcePath);
        setError(null);
        setArchiveInfo(null);
        setScanResults(null);
        setFinalSummary(null);
        setLogs([]);
        setErrorKey(null);
        setProgress(0);
        setProgressInfo({});
        setExecuting(Boolean(inFlightTaskId && currentTaskMode === 'execution'));
        setCheckpointFound(false);
        if (inFlightTaskId) {
            setCurrentTaskId(inFlightTaskId);
            setConflictingTaskId(inFlightTaskId);
            notificationService.info(
                t('incremental_translation.conflicting_task_notice'),
                notificationStyle,
            );
        } else {
            setCurrentTaskId(null);
            setCurrentTaskMode(null);
            setConflictingTaskId(null);
        }
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
                checkCheckpoint(project, nextSourcePath, availableLangs);
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
    }, [
        checkCheckpoint,
        completionSourceRef,
        currentTaskId,
        currentTaskMode,
        notificationStyle,
        t,
    ]);

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
            const res = await translationService.startIncrementalUpdate(
                selectedProject.project_id,
                buildIncrementalUpdatePayload({
                    batchSizeLimit,
                    concurrencyLimit,
                    customSourcePath,
                    dryRun: true,
                    embeddedWorkshopBatchSize,
                    embeddedWorkshopConcurrency,
                    embeddedWorkshopEnabled,
                    embeddedWorkshopFollowPrimary,
                    embeddedWorkshopModel,
                    embeddedWorkshopProvider,
                    embeddedWorkshopRpm,
                    projectId: selectedProject.project_id,
                    rpmLimit,
                    selectedModel,
                    selectedProvider,
                    targetLangCodes,
                    useResume,
                })
            );

            const taskId = res.data.task_id;
            if (taskId) {
                setConflictingTaskId(null);
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
            const detail = err?.response?.data?.detail;
            const duplicateTaskId = detail?.code === 'duplicate_task'
                ? detail.existing_task_id
                : null;
            if (duplicateTaskId) {
                setConflictingTaskId(duplicateTaskId);
                setCurrentTaskId(duplicateTaskId);
                notificationService.info(
                    t('incremental_translation.conflicting_task_notice'),
                    notificationStyle,
                );
            } else {
                notificationService.error(t('notification.error_generic'), notificationStyle);
            }
            setLoading(false);
            preScanInFlightRef.current = false;
        }
    }, [
        selectedProject, customSourcePath, loading, executing, selectedLangs, archiveInfo,
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
            const res = await translationService.startIncrementalUpdate(
                selectedProject.project_id,
                buildIncrementalUpdatePayload({
                    batchSizeLimit,
                    concurrencyLimit,
                    customSourcePath,
                    dryRun: false,
                    embeddedWorkshopBatchSize,
                    embeddedWorkshopConcurrency,
                    embeddedWorkshopEnabled,
                    embeddedWorkshopFollowPrimary,
                    embeddedWorkshopModel,
                    embeddedWorkshopProvider,
                    embeddedWorkshopRpm,
                    projectId: selectedProject.project_id,
                    rpmLimit,
                    selectedModel,
                    selectedProvider,
                    targetLangCodes,
                    useResume,
                })
            );

            const taskId = res.data.task_id;
            if (!taskId) {
                throw new Error(t('incremental_translation.task_id_missing'));
            }

            setConflictingTaskId(null);
            setCurrentTaskId(taskId);
            setCurrentTaskMode('execution');
            connectWebSocket(taskId);
            notificationService.info(
                t('incremental_translation.background_task_notice'),
                notificationStyle,
            );

        } catch (err) {
            const detail = err?.response?.data?.detail;
            const duplicateTaskId = detail?.code === 'duplicate_task'
                ? detail.existing_task_id
                : null;
            if (duplicateTaskId) {
                setConflictingTaskId(duplicateTaskId);
                setCurrentTaskId(duplicateTaskId);
                notificationService.info(
                    t('incremental_translation.conflicting_task_notice'),
                    notificationStyle,
                );
            } else {
                addLog(t('incremental_translation.critical_error', { message: err.message }));
            }
            setExecuting(false);
            executionInFlightRef.current = false;
        }
    }, [
        loading, executing, selectedLangs, archiveInfo, selectedProject,
        selectedProvider, selectedModel, batchSizeLimit, concurrencyLimit, rpmLimit, customSourcePath,
        useResume, embeddedWorkshopEnabled, embeddedWorkshopFollowPrimary, embeddedWorkshopProvider,
        embeddedWorkshopModel, embeddedWorkshopBatchSize, embeddedWorkshopConcurrency, embeddedWorkshopRpm,
        completionSourceRef, connectWebSocket, addLog, notificationStyle, t
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

        const routeState = location.state || {};
        if (!routeSelectionAppliedRef.current && routeState.projectId) {
            const routeProject = projects.find((project) => project.project_id === routeState.projectId);
            if (routeProject) {
                routeSelectionAppliedRef.current = true;
                restorationAppliedRef.current = true;
                resetPersistedState();
                void handleSelectProject(
                    routeProject,
                    routeState.customSourcePath || routeProject.source_path,
                ).then(() => {
                    if (!routeState.taskId) return;
                    const taskMode = routeState.taskMode === 'pre_scan' ? 'pre_scan' : 'execution';
                    statusResyncRef.current = false;
                    setCurrentTaskId(routeState.taskId);
                    setCurrentTaskMode(taskMode);
                    if (taskMode === 'pre_scan') {
                        preScanInFlightRef.current = true;
                        setLoading(true);
                    } else {
                        executionInFlightRef.current = true;
                        setExecuting(true);
                        setActive(3);
                    }
                });
                return;
            }
        }

        const persistedState = persistedStateRef.current;
        if (!persistedState) {
            restorationAppliedRef.current = true;
            return;
        }

        applyIncrementalStateSnapshot(persistedState, {
            setActive,
            setArchiveInfo,
            setCheckpointFound,
            setCheckpointInfo,
            setCurrentTaskId,
            setCurrentTaskMode,
            setCustomSourcePath,
            setEmbeddedWorkshopBatchSize,
            setEmbeddedWorkshopConcurrency,
            setEmbeddedWorkshopEnabled,
            setEmbeddedWorkshopFollowPrimary,
            setEmbeddedWorkshopModel,
            setEmbeddedWorkshopProvider,
            setEmbeddedWorkshopRpm,
            setErrorKey,
            setExecuting,
            setFinalSummary,
            setLoading,
            setLogs,
            setProgress,
            setProgressInfo,
            setScanResults,
            setSelectedLangs,
            setSelectedProject,
            setShowResumeDetails,
            setShowWorkshopSettings,
            setUseResume,
        }, {
            completionSourceRef,
            projects,
        });

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
    }, [completionSourceRef, configLoaded, handleSelectProject, location.state, projects, projectsLoaded, applyProviderSelection, resetPersistedState]);

    // SYNC STATE TO SESSION STORAGE
    useEffect(() => {
        if (!restorationAppliedRef.current) return;

        const stateToPersist = buildIncrementalStateSnapshot({
            active,
            archiveInfo,
            batchSizeLimit,
            checkpointFound,
            checkpointInfo,
            completionSource: completionSourceRef.current,
            concurrencyLimit,
            currentTaskId,
            currentTaskMode,
            customSourcePath,
            embeddedWorkshopBatchSize,
            embeddedWorkshopConcurrency,
            embeddedWorkshopEnabled,
            embeddedWorkshopFollowPrimary,
            embeddedWorkshopModel,
            embeddedWorkshopProvider,
            embeddedWorkshopRpm,
            errorKey,
            executing,
            finalSummary,
            loading,
            logs,
            progress,
            progressInfo,
            rpmLimit,
            scanResults,
            selectedLangs,
            selectedModel,
            selectedProject,
            selectedProvider,
            showResumeDetails,
            showWorkshopSettings,
            useResume,
        });

        try {
            writeIncrementalStateSnapshot(stateToPersist);
        } catch (err) {
            console.warn('Failed to persist incremental translation state:', err);
        }
    }, [
        active, archiveInfo, checkpointFound, checkpointInfo, batchSizeLimit, concurrencyLimit, currentTaskId,
        currentTaskMode, customSourcePath, embeddedWorkshopBatchSize, embeddedWorkshopConcurrency,
        embeddedWorkshopEnabled, embeddedWorkshopFollowPrimary, embeddedWorkshopModel, embeddedWorkshopProvider,
        embeddedWorkshopRpm, executing, finalSummary, loading, logs, progress, progressInfo, rpmLimit, scanResults,
        selectedLangs, selectedModel, selectedProject, selectedProvider, showResumeDetails, showWorkshopSettings,
        completionSourceRef, errorKey, useResume
    ]);

    // LOAD BASICS ON MOUNT
    useEffect(() => {
        try {
            persistedStateRef.current = readIncrementalStateSnapshot();
        } catch (err) {
            console.warn('Failed to read incremental translation persisted state:', err);
            persistedStateRef.current = null;
        }
        fetchProjects();
        fetchApiConfig();
    }, [fetchProjects, fetchApiConfig]);

    // SYNC WORKSHOP CONFIG WITH PRIMARY IF NECESSARY
    useEffect(() => {
        const selection = buildEmbeddedWorkshopSelection({
            providers: apiProviders,
            currentProvider: embeddedWorkshopProvider,
            currentModel: embeddedWorkshopModel,
            followPrimary: embeddedWorkshopFollowPrimary,
        });
        if (selection) {
            setEmbeddedWorkshopProvider(selection.selectedProvider);
            setEmbeddedWorkshopModel(selection.selectedModel);
        }
    }, [
        apiProviders, embeddedWorkshopFollowPrimary, embeddedWorkshopModel, embeddedWorkshopProvider
    ]);

    // RESYNC ONGOING TASK IF RESTORED ACTIVE WORK
    useEffect(() => {
        if (!shouldResyncIncrementalTask({
            currentTaskId,
            currentTaskMode,
            executing,
            loading,
            restorationApplied: restorationAppliedRef.current,
            statusResynced: statusResyncRef.current,
        })) return;

        statusResyncRef.current = true;

        resyncIncrementalTask({
            connectWebSocket,
            currentTaskId,
            currentTaskMode,
            handleTaskUpdate,
            projectService,
        });
    }, [currentTaskId, currentTaskMode, executing, loading, handleTaskUpdate, connectWebSocket]);

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
        executing, progress, progressInfo, logs, finalSummary, currentTaskId, conflictingTaskId,
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
        handleSelectFolder,
        completionSource: completionSourceRef.current,
        resetPersistedState, addLog, getArchivedTargetLanguages
    };
};

export default useIncrementalTranslation;
