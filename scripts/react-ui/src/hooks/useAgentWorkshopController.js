import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { getTutorialKey, useTutorial } from '../context/TutorialContextCore';
import {
  clearAgentWorkshopSnapshot,
  createAgentWorkshopSnapshot,
  readAgentWorkshopSnapshot,
  writeAgentWorkshopSnapshot,
} from './agentWorkshopSession';
import { pollAgentWorkshopRun } from './agentWorkshopRunMonitor';
import {
  buildAgentWorkshopModelOptions,
  createAgentWorkshopIdempotencyKey,
  getAgentWorkshopRunStatus,
  loadAgentWorkshopBootstrap,
  loadAgentWorkshopProjectContext,
  requestAgentWorkshopIssueFix,
  scanAgentWorkshopProject,
  selectAgentWorkshopProvider,
  startAgentWorkshopFixRun,
} from '../services/agentWorkshopWorkflowService';

export const useAgentWorkshopController = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const { setPageContext, startTour } = useTutorial();
  const [active, setActive] = useState(0);
  const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [selectedSidecarPath, setSelectedSidecarPath] = useState(null);
  const [archiveInfo, setArchiveInfo] = useState(null);
  const [projectHistory, setProjectHistory] = useState([]);
  const [issues, setIssues] = useState([]);
  const [fixedIssues, setFixedIssues] = useState([]);
  const [isCached, setIsCached] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [projectContextLoading, setProjectContextLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [gameFilter, setGameFilter] = useState('all');
  const [apiProviders, setApiProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [batchSizeLimit, setBatchSizeLimit] = useState('10');
  const [concurrencyLimit, setConcurrencyLimit] = useState('1');
  const [rpmLimit, setRpmLimit] = useState('40');
  const [executing, setExecuting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [executionStats, setExecutionStats] = useState(null);
  const [currentRunTaskId, setCurrentRunTaskId] = useState(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [workflowError, setWorkflowError] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentIssue, setCurrentIssue] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [fixing, setFixing] = useState(false);
  const restoredRef = useRef(false);
  const runResumeRef = useRef(false);

  const sessionState = useMemo(() => ({
    active,
    selectedProjectId,
    archiveInfo,
    projectHistory,
    issues,
    fixedIssues,
    isCached,
    searchQuery,
    gameFilter,
    selectedProvider,
    selectedModel,
    batchSizeLimit,
    concurrencyLimit,
    rpmLimit,
    executing,
    progress,
    executionLogs,
    executionStats,
    currentRunTaskId,
  }), [
    active,
    selectedProjectId,
    archiveInfo,
    projectHistory,
    issues,
    fixedIssues,
    isCached,
    searchQuery,
    gameFilter,
    selectedProvider,
    selectedModel,
    batchSizeLimit,
    concurrencyLimit,
    rpmLimit,
    executing,
    progress,
    executionLogs,
    executionStats,
    currentRunTaskId,
  ]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId) || null,
    [projects, selectedProjectId]
  );

  const modelOptions = useMemo(() => {
    const provider = apiProviders.find((item) => item.value === selectedProvider);
    return buildAgentWorkshopModelOptions(provider);
  }, [apiProviders, selectedProvider]);

  const filteredProjects = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return projects.filter((project) => {
      const gameOk = gameFilter === 'all' || project.game_id === gameFilter;
      const haystack = [project.name, project.game_id, project.source_language, project.source_path]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return gameOk && (!q || haystack.includes(q));
    });
  }, [gameFilter, projects, searchQuery]);

  const gameFilterOptions = useMemo(() => {
    const games = Array.from(new Set(projects.map((project) => project.game_id).filter(Boolean)));
    return [
      { value: 'all', label: t('common.all_games') },
      ...games.map((game) => ({ value: game, label: game.toUpperCase() })),
    ];
  }, [projects, t]);

  const issueTypeSummary = useMemo(() => {
    const counts = new Map();
    issues.forEach((issue) => {
      const key = issue.error_code || issue.error_type || 'unknown';
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
  }, [issues]);

  const groupedIssues = useMemo(() => {
    const groups = new Map();
    issues.forEach((issue) => {
      const key = issue.file_name || issue.file_path || 'unknown';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(issue);
    });
    return Array.from(groups.entries());
  }, [issues]);

  const persistState = useCallback((override = {}) => {
    writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, override));
  }, [sessionState]);

  const addExecutionLog = useCallback((message) => {
    setExecutionLogs((prev) => {
      const next = [...prev, `[${new Date().toLocaleTimeString()}] ${message}`];
      writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, { executionLogs: next }));
      return next;
    });
  }, [sessionState]);

  const localizeIssueLabel = useCallback((code) => {
    if (!code) return t('agent_workshop.unknown_issue');
    const key = String(code).trim();
    const known = {
      validation_vic3_variable_parity_mismatch: t('agent_workshop.issue_vic3_variable_parity'),
      validation_vic3_color_tags_mismatch: t('agent_workshop.issue_vic3_color_tags'),
      validation_residual_punctuation_found: t('agent_workshop.validation_residual_punctuation_found'),
      validation_invalid_key_format: t('agent_workshop.issue_invalid_key_format'),
      'Invalid key format': t('agent_workshop.issue_invalid_key_format'),
    };
    if (known[key]) return known[key];
    if (key.includes('颜色标签') && key.includes('结束符')) return t('agent_workshop.issue_vic3_color_tags');
    if (key.includes('源语言标点') || key.includes('标点符号')) return t('agent_workshop.validation_residual_punctuation_found');
    if (key.includes('变量数量') || key.includes('变量')) return t('agent_workshop.issue_vic3_variable_parity');
    if (key.startsWith('validation_')) return t('agent_workshop.issue_validation_generic');
    return key;
  }, [t]);

  const localizeIssueDetails = useCallback((issue) => {
    if (!issue) return '';
    const detailsCode = issue.details_code || issue.detailsKey;
    if (detailsCode) {
      return t(`agent_workshop.${detailsCode}`, {
        defaultValue: issue.details || detailsCode,
        ...(issue.details_params || issue.detailsParams || {}),
      });
    }
    return issue.details ? String(issue.details).trim() : '';
  }, [t]);

  const loadProjectContext = useCallback(async (projectId) => {
    setProjectContextLoading(true);
    try {
      const context = await loadAgentWorkshopProjectContext(projectId);
      setArchiveInfo(context.archiveInfo);
      setProjectHistory(context.projectHistory);
    } catch (error) {
      console.error('Failed to load project context', error);
      setArchiveInfo(null);
      setProjectHistory([]);
    } finally {
      setProjectContextLoading(false);
    }
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const { projects: projectList, providers } = await loadAgentWorkshopBootstrap();
        const persisted = readAgentWorkshopSnapshot();
        const routeProjectId = location.state?.projectId || null;
        const routeSidecarPath = location.state?.sidecarPath || null;
        const providerSelection = selectAgentWorkshopProvider({
          providers,
          providerValue: persisted.selectedProvider || providers[0]?.value || '',
          preferredModel: persisted.selectedModel,
        });

        setProjects(projectList);
        setApiProviders(providers);

        if (!restoredRef.current) {
          setActive(routeProjectId ? 1 : (persisted.active ?? 0));
          setSelectedProjectId(routeProjectId || persisted.selectedProjectId || null);
          setSelectedSidecarPath(routeProjectId ? routeSidecarPath : null);
          setArchiveInfo(persisted.archiveInfo || null);
          setProjectHistory(Array.isArray(persisted.projectHistory) ? persisted.projectHistory : []);
          setIssues(Array.isArray(persisted.issues) ? persisted.issues : []);
          setFixedIssues(Array.isArray(persisted.fixedIssues) ? persisted.fixedIssues : []);
          setIsCached(Boolean(persisted.isCached));
          setSearchQuery(persisted.searchQuery || '');
          setGameFilter(persisted.gameFilter || 'all');
          setBatchSizeLimit(persisted.batchSizeLimit || providerSelection.batchSizeLimit);
          setConcurrencyLimit(persisted.concurrencyLimit || '1');
          setRpmLimit(persisted.rpmLimit || '40');
          setExecuting(Boolean(persisted.executing));
          setProgress(persisted.progress || 0);
          setExecutionLogs(Array.isArray(persisted.executionLogs) ? persisted.executionLogs : []);
          setExecutionStats(persisted.executionStats || null);
          setCurrentRunTaskId(persisted.currentRunTaskId || null);
          restoredRef.current = true;
        }

        setSelectedProvider(providerSelection.selectedProvider);
        setSelectedModel(providerSelection.selectedModel);

        if (routeProjectId) {
          await loadProjectContext(routeProjectId);
        }
      } catch (error) {
        console.error('Failed to bootstrap agent workshop', error);
      }
    };
    bootstrap();
  }, [loadProjectContext, location.state]);

  useEffect(() => {
    setPageContext((prev) => {
      const nextContext = `agent-workshop-step-${active}`;
      return prev === nextContext ? prev : nextContext;
    });
  }, [active, setPageContext]);

  useEffect(() => {
    const tutorialKey = getTutorialKey('agent-workshop_prompt_seen');
    if (!localStorage.getItem(tutorialKey)) {
      setShowTutorialPrompt(true);
    }
  }, []);

  useEffect(() => {
    if (restoredRef.current) persistState();
  }, [persistState]);

  const handleProviderChange = useCallback((value) => {
    const providerSelection = selectAgentWorkshopProvider({
      providers: apiProviders,
      providerValue: value || '',
    });
    setSelectedProvider(providerSelection.selectedProvider);
    setSelectedModel(providerSelection.selectedModel);
    setBatchSizeLimit(providerSelection.batchSizeLimit);
  }, [apiProviders]);

  const handleProjectSelect = useCallback(async (projectId) => {
    setSelectedProjectId(projectId);
    setSelectedSidecarPath(null);
    setIssues([]);
    setFixedIssues([]);
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
    setWorkflowError('');
    setIsCached(false);
    setActive(1);
    await loadProjectContext(projectId);
  }, [loadProjectContext]);

  const handleScan = useCallback(async () => {
    if (!selectedProjectId) return;
    setScanLoading(true);
    setWorkflowError('');
    try {
      const nextIssues = await scanAgentWorkshopProject(selectedProjectId, selectedSidecarPath);
      setIssues(nextIssues);
      setIsCached(nextIssues.length > 0);
      setActive(2);
    } catch (error) {
      console.error('Scan failed', error);
      setWorkflowError(error?.response?.data?.detail?.message || error?.response?.data?.detail || error.message || 'Scan failed.');
    } finally {
      setScanLoading(false);
    }
  }, [selectedProjectId, selectedSidecarPath]);

  const openFixModal = useCallback((issue) => {
    setCurrentIssue(issue);
    setFixResult(null);
    setIsModalOpen(true);
  }, []);

  const handleFixRequest = useCallback(async () => {
    if (!selectedProjectId || !currentIssue) return;
    setFixing(true);
    setWorkflowError('');
    try {
      const result = await requestAgentWorkshopIssueFix({
        issue: currentIssue,
        projectId: selectedProjectId,
        selectedModel,
        selectedProvider,
      });
      if (result?.status === 'SUCCESS') {
        setFixedIssues((prev) => [{ ...currentIssue, suggested_fix: result.suggested_fix, report_path: result.report_path }, ...prev]);
        setIssues((prev) => prev.filter((item) => item.key !== currentIssue.key || item.file_name !== currentIssue.file_name));
      }
      setFixResult(result);
    } catch (error) {
      console.error('Fix failed', error);
      setWorkflowError(error?.response?.data?.detail?.message || error?.response?.data?.detail || error.message || 'Fix failed.');
    } finally {
      setFixing(false);
    }
  }, [currentIssue, selectedModel, selectedProjectId, selectedProvider]);

  const applyRunTaskStatus = useCallback((task, runIssues = issues) => {
    const taskProgress = task?.progress || {};
    const resolvedTaskId = task?.task_id || currentRunTaskId;
    if (typeof taskProgress.percent === 'number') {
      setProgress(taskProgress.percent);
    }
    if (Array.isArray(task?.log)) {
      setExecutionLogs(task.log);
    }
    if (task?.summary) {
      const summary = task.summary;
      setExecutionStats({
        total: summary.total || 0,
        completed: summary.completed || 0,
        successCount: summary.successCount || 0,
        failedCount: summary.failedCount || 0,
        durationMs: summary.durationMs || 0,
        batchSize: summary.batchSize || Number(batchSizeLimit) || 10,
        totalBatches: summary.totalBatches || 0,
      });
    }

    if (task?.status === 'completed' || task?.status === 'partial_failed') {
      const results = Array.isArray(task?.summary?.results) ? task.summary.results : [];
      const successfulByKey = new Map(
        results
          .filter((result) => result.status === 'SUCCESS')
          .map((result) => [`${result.file_name}::${result.key}`, result])
      );
      setFixedIssues((prev) => [
        ...runIssues
          .filter((issue) => successfulByKey.has(`${issue.file_name}::${issue.key}`))
          .map((issue) => ({
            ...issue,
            ...successfulByKey.get(`${issue.file_name}::${issue.key}`),
          })),
        ...prev,
      ]);
      setIssues((prev) => prev.filter((issue) => !successfulByKey.has(`${issue.file_name}::${issue.key}`)));
      setProgress(100);
      setExecuting(false);
      persistState({
        active: 3,
        progress: 100,
        executionStats: task.summary,
        executing: false,
        currentRunTaskId: resolvedTaskId,
      });
      return true;
    }

    if (['failed', 'cancelled', 'interrupted'].includes(task?.status)) {
      addExecutionLog(task.message || 'Agent Workshop run failed.');
      setExecuting(false);
      persistState({
        executing: false,
        currentRunTaskId: resolvedTaskId,
      });
      return true;
    }

    return false;
  }, [addExecutionLog, batchSizeLimit, currentRunTaskId, issues, persistState]);

  const applyRunTaskStatusRef = useRef(applyRunTaskStatus);
  const addExecutionLogRef = useRef(addExecutionLog);

  useEffect(() => {
    applyRunTaskStatusRef.current = applyRunTaskStatus;
    addExecutionLogRef.current = addExecutionLog;
  }, [addExecutionLog, applyRunTaskStatus]);

  useEffect(() => {
    if (!restoredRef.current || runResumeRef.current || !executing || !currentRunTaskId) return;

    let cancelled = false;
    runResumeRef.current = true;

    const resumeRun = () => pollAgentWorkshopRun({
      taskId: currentRunTaskId,
      getStatus: getAgentWorkshopRunStatus,
      onTask: (task) => applyRunTaskStatusRef.current(task),
      isCancelled: () => cancelled,
    });

    resumeRun().catch((error) => {
      if (cancelled) return;
      console.error('Failed to resume Agent Workshop run', error);
      const detail = error?.response?.data?.detail;
      addExecutionLogRef.current(detail?.message || detail || error.message || 'Agent Workshop run failed.');
      setWorkflowError(detail?.message || detail || error.message || 'Agent Workshop run failed.');
      setExecuting(false);
    });

    return () => {
      cancelled = true;
    };
  }, [currentRunTaskId, executing]);

  const requestFixRunApproval = useCallback(() => {
    if (!selectedProjectId || !issues.length || !selectedProvider || !selectedModel || executing) return;
    setWorkflowError('');
    setApprovalOpen(true);
  }, [executing, issues.length, selectedModel, selectedProjectId, selectedProvider]);

  const executeFixRun = useCallback(async () => {
    if (!selectedProjectId || !issues.length || !selectedProvider || !selectedModel || executing) return;

    const runIssues = [...issues];
    const idempotencyKey = createAgentWorkshopIdempotencyKey(selectedProjectId);
    setApprovalOpen(false);
    setWorkflowError('');
    runResumeRef.current = false;
    setExecuting(true);
    setProgress(0);
    setExecutionLogs([]);
    setExecutionStats(null);
    setCurrentRunTaskId(null);
    setActive(3);
    writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, {
      active: 3,
      executing: true,
      progress: 0,
      executionLogs: [],
      executionStats: null,
      currentRunTaskId: null,
    }));

    try {
      const run = await startAgentWorkshopFixRun({
        batchSizeLimit,
        concurrencyLimit,
        issues: runIssues,
        projectId: selectedProjectId,
        rpmLimit,
        selectedModel,
        selectedProvider,
        idempotencyKey,
      });
      setCurrentRunTaskId(run.task_id);
      addExecutionLog(`Task accepted: ${run.task_id}`);
      writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, {
        active: 3,
        executing: true,
        currentRunTaskId: run.task_id,
      }));

      await pollAgentWorkshopRun({
        taskId: run.task_id,
        getStatus: getAgentWorkshopRunStatus,
        onTask: (task) => applyRunTaskStatus(task, runIssues),
      });
    } catch (error) {
      console.error('Agent Workshop run failed', error);
      const detail = error?.response?.data?.detail;
      const message = detail?.message || detail || error.message || 'Agent Workshop run failed.';
      addExecutionLog(message);
      setWorkflowError(message);
    } finally {
      setExecuting(false);
    }
  }, [
    addExecutionLog,
    applyRunTaskStatus,
    batchSizeLimit,
    concurrencyLimit,
    executing,
    issues,
    rpmLimit,
    selectedModel,
    selectedProjectId,
    selectedProvider,
    sessionState,
  ]);

  const resetWorkflow = useCallback(() => {
    clearAgentWorkshopSnapshot();
    setActive(0);
    setSelectedProjectId(null);
    setArchiveInfo(null);
    setProjectHistory([]);
    setIssues([]);
    setFixedIssues([]);
    setIsCached(false);
    setSearchQuery('');
    setGameFilter('all');
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
    setExecuting(false);
    setCurrentRunTaskId(null);
    setApprovalOpen(false);
    setWorkflowError('');
  }, []);

  const closeFixModal = useCallback(() => setIsModalOpen(false), []);
  const resetFixResult = useCallback(() => setFixResult(null), []);
  const applyCurrentFixPreview = useCallback(() => {
    setIsModalOpen(false);
    setIssues((prev) => prev.filter((item) => item.key !== currentIssue.key || item.file_name !== currentIssue.file_name));
  }, [currentIssue]);

  const dismissTutorialPrompt = useCallback(() => {
    setShowTutorialPrompt(false);
    localStorage.setItem(getTutorialKey('agent-workshop_prompt_seen'), 'true');
  }, []);

  const confirmTutorialPrompt = useCallback(() => {
    dismissTutorialPrompt();
    startTour();
  }, [dismissTutorialPrompt, startTour]);

  const latestTranslationTime = archiveInfo?.last_upload_at || projectHistory[0]?.timestamp || projectHistory[0]?.created_at;

  return {
    active,
    addExecutionLog,
    approvalOpen,
    apiProviders,
    applyCurrentFixPreview,
    archiveInfo,
    batchSizeLimit,
    closeFixModal,
    concurrencyLimit,
    confirmTutorialPrompt,
    currentIssue,
    currentRunTaskId,
    dismissTutorialPrompt,
    executeFixRun,
    executing,
    executionLogs,
    executionStats,
    filteredProjects,
    fixing,
    fixResult,
    fixedIssues,
    gameFilter,
    gameFilterOptions,
    groupedIssues,
    handleFixRequest,
    handleProjectSelect,
    handleProviderChange,
    handleScan,
    isCached,
    isModalOpen,
    issueTypeSummary,
    issues,
    latestTranslationTime,
    localizeIssueDetails,
    localizeIssueLabel,
    modelOptions,
    openFixModal,
    progress,
    projectContextLoading,
    resetFixResult,
    resetWorkflow,
    requestFixRunApproval,
    rpmLimit,
    scanLoading,
    searchQuery,
    selectedModel,
    selectedProject,
    selectedProjectId,
    selectedProvider,
    setActive,
    setBatchSizeLimit,
    setConcurrencyLimit,
    setGameFilter,
    setRpmLimit,
    setSearchQuery,
    setSelectedModel,
    showTutorialPrompt,
    setApprovalOpen,
    t,
    workflowError,
  };
};
