import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Title, Text, Container, Paper, Button, Group, Select, Badge, Stack, Modal, Code,
  Alert, LoadingOverlay, Box, Stepper, TextInput, SimpleGrid, Card, Progress, Accordion,
} from '@mantine/core';
import {
  IconRobot, IconCheck, IconRefresh, IconInfoCircle, IconSearch, IconWand,
  IconPlayerPlay, IconChartBar, IconSettings, IconFolderCode, IconAlertTriangle,
} from '@tabler/icons-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import styles from './AgentWorkshop.module.css';
import translationStyles from './Translation.module.css';

const STORAGE_KEY = 'agent_workshop_state_v2';
const LOCAL_PROVIDERS = ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];

const AgentWorkshopPage = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const [active, setActive] = useState(0);
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
  const logViewportRef = useRef(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId) || null,
    [projects, selectedProjectId]
  );

  const modelOptions = useMemo(() => {
    const provider = apiProviders.find((item) => item.value === selectedProvider);
    return [...(provider?.available_models || []), ...(provider?.custom_models || [])];
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
    const games = Array.from(new Set(projects.map((p) => p.game_id).filter(Boolean)));
    return [{ value: 'all', label: t('common.all_games') }, ...games.map((game) => ({ value: game, label: game.toUpperCase() }))];
  }, [projects, t]);

  const issueTypeSummary = useMemo(() => {
    const counts = new Map();
    issues.forEach((issue) => {
      const key = issue.error_code || issue.error_type || 'unknown';
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count);
  }, [issues]);

  const localizeIssueLabel = useCallback((code) => {
    if (!code) return t('agent_workshop.unknown_issue');
    const key = String(code).trim();
    const known = {
      validation_vic3_variable_parity_mismatch: t('agent_workshop.issue_vic3_variable_parity'),
      validation_vic3_color_tags_mismatch: t('agent_workshop.issue_vic3_color_tags'),
      validation_invalid_key_format: t('agent_workshop.issue_invalid_key_format'),
      'Invalid key format': t('agent_workshop.issue_invalid_key_format'),
    };
    if (known[key]) return known[key];
    if (key.startsWith('validation_')) {
      return t('agent_workshop.issue_validation_generic');
    }
    return key;
  }, [t]);

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
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      active, selectedProjectId, archiveInfo, projectHistory, issues, fixedIssues, isCached,
      searchQuery, gameFilter, selectedProvider, selectedModel, batchSizeLimit, concurrencyLimit, rpmLimit,
      executing, progress, executionLogs, executionStats, ...override,
    }));
  }, [active, selectedProjectId, archiveInfo, projectHistory, issues, fixedIssues, isCached, searchQuery, gameFilter, selectedProvider, selectedModel, batchSizeLimit, concurrencyLimit, rpmLimit, executing, progress, executionLogs, executionStats]);

  const addExecutionLog = useCallback((message) => {
    setExecutionLogs((prev) => {
      const next = [...prev, `[${new Date().toLocaleTimeString()}] ${message}`];
      const current = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, executionLogs: next }));
      return next;
    });
  }, []);

  useEffect(() => {
    if (logViewportRef.current) {
      logViewportRef.current.scrollTo({ top: logViewportRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [executionLogs]);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const [projectsRes, configRes] = await Promise.all([axios.get('/api/projects'), axios.get('/api/config')]);
        const projectList = projectsRes.data || [];
        const providers = configRes.data?.api_providers || [];
        setProjects(projectList);
        setApiProviders(providers);
        const persisted = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
        const routeProjectId = location.state?.projectId || null;
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
          setBatchSizeLimit(persisted.batchSizeLimit || '10');
          setConcurrencyLimit(persisted.concurrencyLimit || '1');
          setRpmLimit(persisted.rpmLimit || '40');
          setExecuting(Boolean(persisted.executing));
          setProgress(persisted.progress || 0);
          setExecutionLogs(Array.isArray(persisted.executionLogs) ? persisted.executionLogs : []);
          setExecutionStats(persisted.executionStats || null);
          restoredRef.current = true;
        }
        const providerName = persisted.selectedProvider || providers[0]?.value || '';
        const provider = providers.find((item) => item.value === providerName) || providers[0];
        const models = [...(provider?.available_models || []), ...(provider?.custom_models || [])];
        setSelectedProvider(providerName);
        setSelectedModel(persisted.selectedModel || provider?.selected_model || models[0] || '');
        if (routeProjectId) {
          await loadProjectContext(routeProjectId);
        }
      } catch (err) {
        console.error('Failed to bootstrap agent workshop', err);
      }
    };
    bootstrap();
  }, [location.state]);

  useEffect(() => {
    if (restoredRef.current) persistState();
  }, [persistState]);

  const handleProviderChange = (value) => {
    setSelectedProvider(value || '');
    const provider = apiProviders.find((item) => item.value === value);
    const models = [...(provider?.available_models || []), ...(provider?.custom_models || [])];
    setSelectedModel(provider?.selected_model || models[0] || '');
    setBatchSizeLimit(LOCAL_PROVIDERS.includes(value || '') ? '3' : '10');
  };

  const loadProjectContext = async (projectId) => {
    setProjectContextLoading(true);
    try {
      const [archiveRes, historyRes] = await Promise.all([
        axios.get(`/api/project/${projectId}/check-archive`),
        axios.get(`/api/project/${projectId}/history`),
      ]);
      setArchiveInfo(archiveRes.data || null);
      setProjectHistory(Array.isArray(historyRes.data) ? historyRes.data : []);
    } catch (err) {
      console.error('Failed to load project context', err);
      setArchiveInfo(null);
      setProjectHistory([]);
    } finally {
      setProjectContextLoading(false);
    }
  };

  const handleProjectSelect = async (projectId) => {
    setSelectedProjectId(projectId);
    setIssues([]);
    setFixedIssues([]);
    setExecutionLogs([]);
    setExecutionStats(null);
    setProgress(0);
    setIsCached(false);
    setActive(1);
    await loadProjectContext(projectId);
  };

  const handleScan = async () => {
    if (!selectedProjectId) return;
    setScanLoading(true);
    try {
      const res = await axios.get(`/api/agent-workshop/scan?project_id=${selectedProjectId}`);
      setIssues(Array.isArray(res.data) ? res.data : []);
      setIsCached((res.data || []).length > 0);
      setActive(2);
    } catch (err) {
      console.error('Scan failed', err);
    } finally {
      setScanLoading(false);
    }
  };

  const openFixModal = (issue) => {
    setCurrentIssue(issue);
    setFixResult(null);
    setIsModalOpen(true);
  };

  const handleFixRequest = async () => {
    if (!selectedProjectId || !currentIssue) return;
    setFixing(true);
    try {
      const res = await axios.post('/api/agent-workshop/fix', {
        project_id: selectedProjectId,
        api_provider: selectedProvider,
        api_model: selectedModel,
        ...currentIssue,
      });
      if (res.data?.status === 'SUCCESS') {
        setFixedIssues((prev) => [{ ...currentIssue, suggested_fix: res.data.suggested_fix, report_path: res.data.report_path }, ...prev]);
        setIssues((prev) => prev.filter((item) => item.key !== currentIssue.key || item.file_name !== currentIssue.file_name));
      }
      setFixResult(res.data);
    } catch (err) {
      console.error('Fix failed', err);
    } finally {
      setFixing(false);
    }
  };

  const executeFixRun = async () => {
    if (!selectedProjectId || !issues.length || !selectedProvider || !selectedModel || executing) return;
    const batchSize = Math.max(1, Number(batchSizeLimit) || (LOCAL_PROVIDERS.includes(selectedProvider) ? 3 : 10));
    const total = issues.length;
    const concurrency = Math.max(1, Number(concurrencyLimit) || 1);
    const rpm = Math.max(1, Number(rpmLimit) || 1);
    const intervalMs = Math.ceil(60000 / rpm);
    const snapshot = [...issues];
    const batches = Array.from({ length: Math.ceil(snapshot.length / batchSize) }, (_, index) =>
      snapshot.slice(index * batchSize, (index + 1) * batchSize)
    );
    let nextBatchIndex = 0;
    let nextDispatchAt = Date.now();
    let completed = 0;
    let successCount = 0;
    let failedCount = 0;
    const startedAt = Date.now();
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    setExecuting(true);
    setProgress(0);
    setExecutionLogs([]);
    setExecutionStats(null);
    setActive(3);
    addExecutionLog(`Starting fix run for ${total} issue(s) in ${batches.length} batch(es) of up to ${batchSize}.`);
    if (LOCAL_PROVIDERS.includes(selectedProvider) && batchSize < 10) {
      addExecutionLog(`Using smaller local batches to avoid context overflow on the selected local model.`);
    }

    const claimBatch = async () => {
      if (nextBatchIndex >= batches.length) return null;
      const batchNumber = nextBatchIndex + 1;
      const batch = batches[nextBatchIndex++];
      const now = Date.now();
      const waitMs = Math.max(0, nextDispatchAt - now);
      nextDispatchAt = Math.max(now, nextDispatchAt) + intervalMs;
      if (waitMs > 0) await sleep(waitMs);
      return { batchNumber, batch };
    };

    const worker = async (workerId) => {
      while (true) {
        const claimed = await claimBatch();
        if (!claimed) return;
        const { batchNumber, batch } = claimed;
        addExecutionLog(`Worker ${workerId}: fixing batch ${batchNumber}/${batches.length} (${batch.length} issue(s))`);
        try {
          const res = await axios.post('/api/agent-workshop/fix-batch', {
            project_id: selectedProjectId,
            api_provider: selectedProvider,
            api_model: selectedModel,
            issues: batch,
          });
          const results = Array.isArray(res.data?.results) ? res.data.results : [];
          const fixedByKey = new Map(results.map((item) => [`${item.file_name}::${item.key}`, item]));
          batch.forEach((issue) => {
            const result = fixedByKey.get(`${issue.file_name}::${issue.key}`);
            if (result?.status === 'SUCCESS') {
              successCount += 1;
              setFixedIssues((prev) => [{ ...issue, suggested_fix: result.suggested_fix, report_path: result.report_path }, ...prev]);
              setIssues((prev) => prev.filter((item) => item.key !== issue.key || item.file_name !== issue.file_name));
            } else {
              failedCount += 1;
            }
          });
          addExecutionLog(`Batch ${batchNumber} completed: ${results.filter((item) => item.status === 'SUCCESS').length}/${batch.length} fixed.`);
        } catch (err) {
          failedCount += batch.length;
          addExecutionLog(`Batch ${batchNumber} failed: ${err?.response?.data?.detail || err.message}`);
        } finally {
          completed += batch.length;
          const stats = { total, completed, successCount, failedCount, durationMs: Date.now() - startedAt, batchSize, totalBatches: batches.length };
          const percent = Math.round((completed / total) * 100);
          setProgress(percent);
          setExecutionStats(stats);
          persistState({ active: 3, progress: percent, executionStats: stats, executing: true });
        }
      }
    };

    try {
      await Promise.all(Array.from({ length: Math.min(concurrency, batches.length) }, (_, idx) => worker(idx + 1)));
    } finally {
      const stats = { total, completed: total, successCount, failedCount, durationMs: Date.now() - startedAt, batchSize, totalBatches: batches.length };
      setExecutionStats(stats);
      setProgress(100);
      setExecuting(false);
      addExecutionLog('Fix run completed.');
      persistState({ active: 3, progress: 100, executionStats: stats, executing: false });
    }
  };

  const resetWorkflow = () => {
    sessionStorage.removeItem(STORAGE_KEY);
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
  };

  const latestTranslationTime = archiveInfo?.last_upload_at || projectHistory[0]?.timestamp || projectHistory[0]?.created_at;

  return (
    <Box className={styles.container}>
      <Container size="xl" py="lg">
        <Stack gap="lg">
          <Stack gap={0}>
            <Title order={2} className={styles.title}><IconRobot size={28} style={{ marginRight: 12, verticalAlign: 'middle' }} />{t('page_title_agent_workshop')}</Title>
            <Text size="sm" c="dimmed">{t('agent_workshop.description')}</Text>
          </Stack>

          <Stepper active={active} onStepClick={setActive} allowNextStepsSelect={false} breakpoint="sm">
            <Stepper.Step label={t('agent_workshop.step_select_project')} description={t('agent_workshop.step_select_project_desc')} icon={<IconFolderCode size={18} />}>
              <Stack mt="xl" className={translationStyles.executionStep}>
                <Paper withBorder p="md" radius="md" className={translationStyles.glassCard}>
                  <Group grow align="flex-end">
                    <TextInput label={t('common.search')} placeholder={t('agent_workshop.project_search_placeholder')} value={searchQuery} onChange={(e) => setSearchQuery(e.currentTarget.value)} leftSection={<IconSearch size={16} />} />
                    <Select label={t('common.filter_game')} data={gameFilterOptions} value={gameFilter} onChange={(value) => setGameFilter(value || 'all')} />
                  </Group>
                </Paper>
                <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                  {filteredProjects.map((project) => (
                    <Card key={project.project_id} padding="lg" radius="md" withBorder onClick={() => handleProjectSelect(project.project_id)} style={{ cursor: 'pointer' }} className={selectedProjectId === project.project_id ? translationStyles.selectedCard : translationStyles.glassCard}>
                      <Stack gap="xs">
                        <Box><Title order={5}>{project.name}</Title><Text size="xs" c="dimmed">{project.source_path?.split(/[\\/]/).pop()}</Text></Box>
                        <Group gap="xs"><Badge color="blue" variant="light">{project.game_id}</Badge><Badge color="teal" variant="light">{project.source_language || '--'}</Badge></Group>
                        <Text size="xs" c="dimmed" lineClamp={2}>{project.source_path}</Text>
                      </Stack>
                    </Card>
                  ))}
                </SimpleGrid>
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_project_summary')} description={t('agent_workshop.step_project_summary_desc')} icon={<IconSettings size={18} />}>
              <Stack mt="xl" gap="md">
                {projectContextLoading && <Paper withBorder p="lg" radius="md" className={translationStyles.glassCard}><Text size="sm">{t('common.loading')}</Text></Paper>}
                {selectedProject && <Paper withBorder p="lg" radius="md" className={translationStyles.glassCard}><Stack>
                  <Group justify="space-between"><Title order={4}>{selectedProject.name}</Title><Badge color="blue" variant="light">{selectedProject.game_id}</Badge></Group>
                  <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.project_source_language')}</Text><Text size="sm" fw={600}>{selectedProject.source_language || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.archived_target_languages')}</Text><Text size="sm" fw={600}>{(archiveInfo?.archived_languages || []).join(', ') || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.project_game')}</Text><Text size="sm" fw={600}>{selectedProject.game_id || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.last_translation_time')}</Text><Text size="sm" fw={600}>{latestTranslationTime ? new Date(latestTranslationTime).toLocaleString() : '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.source_entries')}</Text><Text size="sm" fw={600}>{archiveInfo?.source_entry_count ?? '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.translation_entries')}</Text><Text size="sm" fw={600}>{archiveInfo?.total_translation_entries ?? '--'}</Text></Card>
                  </SimpleGrid>
                  <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.project_path')}</Text><Text size="sm" fw={500}>{selectedProject.source_path}</Text></Card>
                  <Alert icon={<IconInfoCircle size={16} />} color="blue" radius="md"><Text size="sm">{t('agent_workshop.scan_help')}</Text></Alert>
                  <Group justify="space-between"><Button variant="light" onClick={() => setActive(0)}>{t('common.back')}</Button><Button leftSection={<IconSearch size={16} />} onClick={handleScan} loading={scanLoading}>{t('agent_workshop.scan_btn')}</Button></Group>
                </Stack></Paper>}
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_scan_summary')} description={t('agent_workshop.step_scan_summary_desc')} icon={<IconChartBar size={18} />}>
              <Stack mt="xl" gap="md">
                <Paper withBorder p="lg" radius="md" className={translationStyles.glassCard}>
                  <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} mb="lg">
                    <Select label={t('agent_workshop.provider_label')} data={apiProviders} value={selectedProvider} onChange={handleProviderChange} />
                    <Select label={t('agent_workshop.model_label')} data={modelOptions} value={selectedModel} onChange={setSelectedModel} searchable />
                    <Select label={t('agent_workshop.batch_size')} data={['1', '3', '10', '20'].map((value) => ({ value, label: value }))} value={batchSizeLimit} onChange={setBatchSizeLimit} />
                    <Select label={t('incremental_translation.concurrency_limit')} data={['1', '2', '3', '5', '10'].map((value) => ({ value, label: value }))} value={concurrencyLimit} onChange={setConcurrencyLimit} />
                    <Select label={t('incremental_translation.rpm_limit')} data={['5', '10', '20', '30', '40', '60'].map((value) => ({ value, label: value }))} value={rpmLimit} onChange={setRpmLimit} />
                  </SimpleGrid>
                  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="lg">
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.total_entries')}</Text><Title order={3}>{archiveInfo?.source_entry_count ?? '--'}</Title></Card>
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.issue_entries')}</Text><Title order={3} c={issues.length ? 'orange' : 'green'}>{issues.length}</Title></Card>
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.cached_state')}</Text><Title order={5}>{isCached ? t('agent_workshop.cached_label') : t('agent_workshop.scanned_label')}</Title></Card>
                  </SimpleGrid>
                  <Alert icon={<IconAlertTriangle size={16} />} color={issues.length ? 'orange' : 'green'} radius="md">{issues.length ? t('agent_workshop.start_fix_confirm') : t('agent_workshop.no_errors_desc')}</Alert>
                  <Group justify="flex-end" mt="md"><Button variant="light" onClick={() => setActive(1)}>{t('common.back')}</Button><Button leftSection={<IconPlayerPlay size={18} />} onClick={executeFixRun} disabled={!issues.length || !selectedProvider || !selectedModel || executing}>{t('agent_workshop.start_fix')}</Button></Group>
                  {issueTypeSummary.length > 0 && <Stack gap="xs" mt="xl"><Text size="sm" fw={600}>{t('agent_workshop.issue_type_summary')}</Text><SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>{issueTypeSummary.map((item) => <Card key={item.label} withBorder p="sm" radius="md"><Text size="xs" c="dimmed" lineClamp={2}>{localizeIssueLabel(item.label)}</Text><Text size="sm" fw={700}>{item.count}</Text></Card>)}</SimpleGrid></Stack>}
                  {groupedIssues.length > 0 && <Accordion variant="separated" radius="md" mt="xl"><Accordion.Item value="file-details"><Accordion.Control><Group justify="space-between" wrap="nowrap"><Text fw={600}>{t('agent_workshop.file_issue_details')}</Text><Badge color="orange" variant="light">{groupedIssues.length}</Badge></Group></Accordion.Control><Accordion.Panel><Stack gap="sm">{groupedIssues.map(([fileKey, fileIssues]) => <Accordion key={fileKey} variant="contained" radius="md"><Accordion.Item value={fileKey}><Accordion.Control><Group justify="space-between" wrap="nowrap"><Box style={{ minWidth: 0 }}><Text size="sm" fw={600} truncate>{fileKey}</Text><Text size="xs" c="dimmed">{fileIssues[0]?.target_lang || '--'}</Text></Box><Badge color="orange" variant="light">{fileIssues.length}</Badge></Group></Accordion.Control><Accordion.Panel><Stack gap="sm">{fileIssues.map((issue, index) => <Paper key={`${issue.file_name}:${issue.key}:${index}`} p="sm" withBorder><Group justify="space-between" align="flex-start" wrap="nowrap"><Box style={{ minWidth: 0, flex: 1 }}><Text size="sm" fw={600}>{issue.key}</Text><Badge color="red" variant="light" mt={6}>{localizeIssueLabel(issue.error_code || issue.error_type)}</Badge><Text size="xs" c="dimmed" mt={8}>{issue.details}</Text><Code block mt="sm">{issue.target_str}</Code></Box><Button size="xs" variant="light" leftSection={<IconWand size={14} />} onClick={() => openFixModal(issue)} style={{ whiteSpace: 'nowrap' }}>{t('agent_workshop.fix_btn')}</Button></Group></Paper>)}</Stack></Accordion.Panel></Accordion.Item></Accordion>)}</Stack></Accordion.Panel></Accordion.Item></Accordion>}
                </Paper>
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_execution')} description={t('agent_workshop.step_execution_desc')} icon={<IconRobot size={18} />}>
              <Stack mt="xl"><Paper withBorder p="xl" radius="md" className={translationStyles.glassCard}>
                <Title order={4} mb="md">{t('agent_workshop.execution_title')}</Title>
                <Progress value={progress} label={progress > 0 ? `${progress}%` : ''} size="xl" radius="xl" animated={executing} mb="sm" />
                <Group justify="space-between" mb="xl"><Box><Text size="sm" fw={600}>{executing ? t('agent_workshop.execution_in_progress') : t('agent_workshop.execution_completed')}</Text><Text size="xs" c="dimmed">{executionStats ? `${executionStats.completed} / ${executionStats.total}` : t('agent_workshop.execution_pending')}</Text></Box><Text size="xs" fw={700} c="blue">{progress}%</Text></Group>
                <Box ref={logViewportRef} className={translationStyles.logScrollBox}>{executionLogs.map((log, index) => <Text key={`${log}-${index}`} size="xs" style={{ fontFamily: 'monospace' }} mb={2}>{log}</Text>)}</Box>
              {executionStats && !executing && <Stack mt="xl"><SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md"><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.fixed_count')}</Text><Title order={3} c="green">{executionStats.successCount}</Title></Card><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.failed_count')}</Text><Title order={3} c="orange">{executionStats.failedCount}</Title></Card><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.duration')}</Text><Title order={5}>{`${(executionStats.durationMs / 1000).toFixed(1)} s`}</Title></Card></SimpleGrid>
                {fixedIssues.length > 0 && (
                  <Accordion variant="separated" radius="md">
                    <Accordion.Item value="diff-preview">
                      <Accordion.Control>{t('agent_workshop.diff_preview')}</Accordion.Control>
                      <Accordion.Panel>
                        <Stack gap="md">
                          {fixedIssues.map((issue, index) => (
                            <Paper key={`${issue.file_name}:${issue.key}:${index}`} withBorder p="md" radius="md">
                              <Stack gap="xs">
                                <Group justify="space-between" wrap="nowrap">
                                  <Box style={{ minWidth: 0 }}>
                                    <Text size="sm" fw={700}>{issue.key}</Text>
                                    <Text size="xs" c="dimmed" truncate>{issue.file_name}</Text>
                                  </Box>
                                  <Badge color="green" variant="light">{localizeIssueLabel(issue.error_code || issue.error_type)}</Badge>
                                </Group>
                                <Text size="xs" c="dimmed">{issue.details}</Text>
                                <Text size="xs" fw={700}>{t('agent_workshop.before_fix')}</Text>
                                <Code block>{issue.target_str}</Code>
                                <Text size="xs" fw={700}>{t('agent_workshop.after_fix')}</Text>
                                <Code block>{issue.suggested_fix}</Code>
                                {issue.report_path && <Text size="xs" c="dimmed">{t('agent_workshop.report_path')}: {issue.report_path}</Text>}
                              </Stack>
                            </Paper>
                          ))}
                        </Stack>
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                )}
                <Group><Button onClick={resetWorkflow}>{t('common.finish')}</Button></Group></Stack>}
              </Paper></Stack>
            </Stepper.Step>
          </Stepper>
        </Stack>

        <Modal opened={isModalOpen} onClose={() => setIsModalOpen(false)} title={<Group gap="xs"><IconRobot size={20} /><Text fw={600}>{t('agent_workshop.modal_title')}</Text></Group>} size="lg">
          <Box style={{ position: 'relative' }}>
            <LoadingOverlay visible={fixing} overlayBlur={2} />
            <Stack gap="md">
              <Paper p="xs" withBorder><Text size="xs" fw={700} c="dimmed" tt="uppercase">{t('agent_workshop.modal_source_context')}</Text><Code block>{currentIssue?.source_str || t('agent_workshop.no_source_context')}</Code></Paper>
              <Paper p="xs" withBorder><Text size="xs" fw={700} c="red" tt="uppercase">{t('agent_workshop.modal_error_detected')}</Text><Code block color="red">{currentIssue?.target_str}</Code><Text size="xs" mt={4}>{currentIssue?.details}</Text></Paper>
              {!fixResult && <Button fullWidth variant="gradient" gradient={{ from: 'indigo', to: 'cyan' }} onClick={handleFixRequest} disabled={fixing || !selectedProvider}>{selectedProvider ? t('agent_workshop.fix_btn') : t('agent_workshop.select_model_hint')}</Button>}
              {fixResult && <Stack gap="md"><Alert icon={<IconInfoCircle size={16} />} title={t('agent_workshop.modal_analysis')} color="indigo" variant="light"><Text size="sm" fs="italic">{fixResult.reflection}</Text>{fixResult.report_path && <Text size="xs" mt={8} c="dimmed">{t('agent_workshop.report_path')}: {fixResult.report_path}</Text>}</Alert><Paper p="xs" withBorder style={{ backgroundColor: 'rgba(40, 167, 69, 0.05)' }}><Text size="xs" fw={700} c="green" tt="uppercase">{t('agent_workshop.modal_suggestion')}</Text><Code block color="green">{fixResult.suggested_fix}</Code>{fixResult.parity_message && <Text size="xs" mt={4} c={fixResult.status === 'SUCCESS' ? 'green' : 'orange'}><IconCheck size={12} /> {fixResult.parity_message}</Text>}</Paper><Group grow mt="lg"><Button variant="subtle" onClick={() => setFixResult(null)}>{t('agent_workshop.regenerate')}</Button><Button color="green" onClick={() => { setIsModalOpen(false); setIssues((prev) => prev.filter((item) => item.key !== currentIssue.key || item.file_name !== currentIssue.file_name)); }}>{t('agent_workshop.apply_fix')}</Button></Group></Stack>}
            </Stack>
          </Box>
        </Modal>
      </Container>
    </Box>
  );
};

export default AgentWorkshopPage;
