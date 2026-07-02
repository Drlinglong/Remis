import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { getTutorialKey, useTutorial } from '../context/TutorialContextCore';
import {
  appendAgentWorkshopLogSnapshot,
  clearAgentWorkshopSnapshot,
  createAgentWorkshopSnapshot,
  readAgentWorkshopSnapshot,
  writeAgentWorkshopSnapshot,
} from './agentWorkshopSession';
import {
  buildAgentWorkshopModelOptions,
  loadAgentWorkshopBootstrap,
  loadAgentWorkshopProjectContext,
  requestAgentWorkshopIssueFix,
  runAgentWorkshopFixBatches,
  scanAgentWorkshopProject,
  selectAgentWorkshopProvider,
} from '../services/agentWorkshopWorkflowService';

export const useAgentWorkshopController = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const { setPageContext, startTour } = useTutorial();
  const [active, setActive] = useState(0);
  const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
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
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentIssue, setCurrentIssue] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [fixing, setFixing] = useState(false);
  const restoredRef = useRef(false);

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
    setIssues([]);
    setFixedIssues([]);
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
    setIsCached(false);
    setActive(1);
    await loadProjectContext(projectId);
  }, [loadProjectContext]);

  const handleScan = useCallback(async () => {
    if (!selectedProjectId) return;
    setScanLoading(true);
    try {
      const nextIssues = await scanAgentWorkshopProject(selectedProjectId);
      setIssues(nextIssues);
      setIsCached(nextIssues.length > 0);
      setActive(2);
    } catch (error) {
      console.error('Scan failed', error);
    } finally {
      setScanLoading(false);
    }
  }, [selectedProjectId]);

  const openFixModal = useCallback((issue) => {
    setCurrentIssue(issue);
    setFixResult(null);
    setIsModalOpen(true);
  }, []);

  const handleFixRequest = useCallback(async () => {
    if (!selectedProjectId || !currentIssue) return;
    setFixing(true);
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
    } finally {
      setFixing(false);
    }
  }, [currentIssue, selectedModel, selectedProjectId, selectedProvider]);

  const executeFixRun = useCallback(async () => {
    if (!selectedProjectId || !issues.length || !selectedProvider || !selectedModel || executing) return;

    setExecuting(true);
    setProgress(0);
    setExecutionLogs([]);
    setExecutionStats(null);
    setActive(3);
    writeAgentWorkshopSnapshot(createAgentWorkshopSnapshot(sessionState, {
      active: 3,
      executing: true,
      progress: 0,
      executionLogs: [],
      executionStats: null,
    }));

    try {
      const stats = await runAgentWorkshopFixBatches({
        addExecutionLog: (message) => {
          setExecutionLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
          appendAgentWorkshopLogSnapshot(message);
        },
        batchSizeLimit,
        concurrencyLimit,
        issues,
        onIssueFixed: (issue, result) => {
          setFixedIssues((prev) => [{ ...issue, suggested_fix: result.suggested_fix, report_path: result.report_path }, ...prev]);
          setIssues((prev) => prev.filter((item) => item.key !== issue.key || item.file_name !== issue.file_name));
        },
        onProgress: ({ percent, stats: nextStats }) => {
          setProgress(percent);
          setExecutionStats(nextStats);
          persistState({ active: 3, progress: percent, executionStats: nextStats, executing: true });
        },
        projectId: selectedProjectId,
        rpmLimit,
        selectedModel,
        selectedProvider,
      });

      setExecutionStats(stats);
      setProgress(100);
      setExecuting(false);
      addExecutionLog('Fix run completed.');
      persistState({ active: 3, progress: 100, executionStats: stats, executing: false });
    } finally {
      setExecuting(false);
    }
  }, [
    addExecutionLog,
    batchSizeLimit,
    concurrencyLimit,
    executing,
    issues,
    persistState,
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
    apiProviders,
    applyCurrentFixPreview,
    archiveInfo,
    batchSizeLimit,
    closeFixModal,
    concurrencyLimit,
    confirmTutorialPrompt,
    currentIssue,
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
    t,
  };
};
