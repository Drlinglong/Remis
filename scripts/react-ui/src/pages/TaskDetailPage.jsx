import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Code,
  Divider,
  Grid,
  Group,
  Loader,
  Menu,
  Paper,
  Progress,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArchive,
  IconArrowUpRight,
  IconArrowBackUp,
  IconCheck,
  IconClock,
  IconDots,
  IconDownload,
  IconFolderOpen,
  IconHistory,
  IconInfoCircle,
  IconPlayerPlay,
  IconRefresh,
  IconRestore,
  IconTool,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { useTaskCenter } from '../context/TaskCenterContextCore';
import { useTutorial } from '../context/TutorialContextCore';
import GlossaryHealthPenaltyBreakdown from '../components/glossary/GlossaryHealthPenaltyBreakdown';
import api from '../utils/api';
import { getGameBadgeColor } from '../utils/gamePresentation';
import { formatLocalizedDateTime } from '../utils/localizedDateTime';
import { buildProofreadingUrl } from '../utils/proofreadingLinks';
import { ACTIVE_TASK_STATUSES, formatTaskDuration, taskDurationMs } from '../utils/taskTime';
import {
  getTaskEventPresentation,
  getTaskNextStep,
  getTaskResultSummary,
  getTaskStageLabel,
  sortTaskEventsNewestFirst,
} from '../utils/taskPresentation';
import { glossaryHealthReviewRoute, taskDetailRoute, taskWorkflowTarget } from '../utils/taskRoutes';
import styles from './TaskDetailPage.module.css';
const STATUS_COLORS = {
  queued: 'gray',
  running: 'blue',
  awaiting_approval: 'yellow',
  completed: 'green',
  failed: 'red',
  interrupted: 'orange',
  cancelled: 'gray',
  unknown: 'gray',
};

const EVENT_COLORS = {
  error: 'red',
  warning: 'yellow',
  success: 'green',
  info: 'blue',
  debug: 'gray',
};

const ACTIVE_TASK_REFRESH_INTERVAL_MS = 4000;

const formatTimestamp = (value, locale) => {
  if (!value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return formatLocalizedDateTime(parsed, locale);
};

const localizeGlossaryHealthEvent = (event, t, isPartial) => {
  if (isPartial && event.level === 'error') {
    return t('glossary_health_ai_unavailable_event');
  }

  const message = String(event.message || '');
  if (message === 'Glossary health check queued.') {
    return t('glossary_health_event_queued');
  }
  if (message === 'Deterministic glossary checks started.') {
    return t('glossary_health_event_deterministic_started');
  }
  const findingsMatch = message.match(/^Deterministic checks found (\d+) issue\(s\)\.$/);
  if (findingsMatch) {
    return t('glossary_health_event_deterministic_found', {
      count: Number(findingsMatch[1]),
    });
  }
  if (message === 'Explicitly approved advisory model review started.') {
    return t('glossary_health_event_ai_started');
  }
  if (message === 'Health report completed without changing glossary data.') {
    return t('glossary_health_completed_title');
  }
  return message;
};

function useLiveClock(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

export default function TaskDetailPage() {
  const { taskId = '' } = useParams();
  const decodedTaskId = taskId;
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { openTaskCenter, refreshTasks } = useTaskCenter();
  const { setPageContext } = useTutorial();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mutating, setMutating] = useState(false);
  const [logExpanded, setLogExpanded] = useState(false);
  const [actionError, setActionError] = useState('');

  const loadTask = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const response = await api.get(`/api/tasks/${encodeURIComponent(decodedTaskId)}`, {
        params: { include_diagnostics: true },
      });
      setTask(response.data);
      setError('');
    } catch (loadError) {
      setError(loadError.response?.data?.detail || loadError.message || t('task_detail.load_error'));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [decodedTaskId, t]);

  useEffect(() => {
    loadTask();
  }, [loadTask]);

  useEffect(() => {
    setPageContext('task-detail');
  }, [setPageContext]);

  const taskStatus = task?.status;

  useEffect(() => {
    setLogExpanded(['failed', 'interrupted'].includes(taskStatus));
  }, [decodedTaskId, taskStatus]);

  useEffect(() => {
    if (!ACTIVE_TASK_STATUSES.has(taskStatus)) return undefined;
    let socket;
    let retryTimer;
    let refreshTimer;
    let pollTimer;
    let cancelled = false;

    const scheduleRefresh = () => {
      if (refreshTimer || cancelled) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null;
        loadTask({ quiet: true });
      }, 200);
    };

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const backendPort = import.meta.env.VITE_BACKEND_PORT || '1453';
      socket = new WebSocket(`${protocol}//127.0.0.1:${backendPort}/api/ws/status/${encodeURIComponent(decodedTaskId)}`);
      socket.onmessage = scheduleRefresh;
      socket.onerror = scheduleRefresh;
      socket.onclose = () => {
        if (!cancelled) retryTimer = window.setTimeout(connect, 1500);
      };
    };

    connect();
    pollTimer = window.setInterval(scheduleRefresh, ACTIVE_TASK_REFRESH_INTERVAL_MS);
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') scheduleRefresh();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (refreshTimer) window.clearTimeout(refreshTimer);
      if (pollTimer) window.clearInterval(pollTimer);
      document.removeEventListener('visibilitychange', handleVisibility);
      socket?.close();
    };
  }, [decodedTaskId, loadTask, taskStatus]);

  const active = ACTIVE_TASK_STATUSES.has(taskStatus);
  const now = useLiveClock(active);
  const duration = formatTaskDuration(taskDurationMs(task, now));
  const kindLabel = task ? t(`task_center.kind.${task.kind}`, { defaultValue: task.title }) : '';
  const statusLabel = task ? t(`task_center.status.${task.status}`, { defaultValue: task.status }) : '';
  const creatorLabel = task?.created_by?.label || t(`task_center.creator.${task?.created_by?.type || 'system'}`);
  const projectName = task?.project_context?.name;
  const gameId = task?.project_context?.game_id;
  const gameName = gameId ? t(`game_name_${String(gameId).toLowerCase()}`, { defaultValue: gameId }) : '';
  const resultMetadata = task?.result?.metadata || {};
  const workshopRepairResults = ['agent_workshop', 'agent_workshop_batch'].includes(task?.kind)
    && Array.isArray(resultMetadata.results)
    ? resultMetadata.results
    : [];
  const healthMetadata = resultMetadata.preview || resultMetadata;
  const resultTypes = new Set(task?.result?.types || []);
  const isGlossaryHealthResult = resultTypes.has('glossary_health_report');
  const isGlossaryMergeResult = resultTypes.has('glossary_merge');
  const isPartialGlossaryHealth = (
    task?.kind === 'glossary_health_check'
    && isGlossaryHealthResult
    && resultMetadata.ai_review_status === 'failed'
  );
  const displayStatusLabel = isPartialGlossaryHealth
    ? t('glossary_health_partial_status')
    : statusLabel;
  const displayStatusColor = isPartialGlossaryHealth
    ? 'orange'
    : (STATUS_COLORS[task?.status] || 'gray');
  const localizedTaskTitle = ['agent_workshop', 'agent_workshop_batch', 'repair'].includes(task?.kind)
    ? t('agent_workshop.description')
    : task?.kind === 'incremental_translation'
      ? t('task_center.kind.incremental_translation')
    : task?.kind === 'glossary_health_check'
      ? t('glossary_health_task_title', {
        count: healthMetadata.glossary_count || 1,
        defaultValue: task.title,
      })
      : task?.title;
  const localizedResultSummary = (
    task?.kind === 'glossary_health_check'
    && Number.isFinite(Number(healthMetadata.score))
  )
    ? t('glossary_health_completed_message', {
      score: healthMetadata.score,
      count: healthMetadata.issue_count || 0,
    })
    : getTaskResultSummary(task, t);
  const localizedTaskStage = getTaskStageLabel(task, t);
  const localizedNextStep = getTaskNextStep(task, t);
  const localizedBlockingReason = task?.blocking_reason_code === 'project_write_locked'
    ? t('task_detail.blocking_description')
    : (task?.blocking_reason || t('task_detail.blocking_description'));
  const presentedEvents = useMemo(() => (
    sortTaskEventsNewestFirst(task?.events || []).map((event) => {
      if (task?.kind === 'glossary_health_check') {
        return {
          event,
          message: localizeGlossaryHealthEvent(event, t, isPartialGlossaryHealth),
          technical: event.audience === 'diagnostic',
        };
      }
      return {
        event,
        ...getTaskEventPresentation(event, task, t),
      };
    })
  ), [isPartialGlossaryHealth, task, t]);
  const visibleEvents = presentedEvents;
  const hasGlossaryHealthCases = (resultMetadata.issues || []).some((issue) => (
    (issue.items || []).length > 0
  ));

  const mutateArchive = async (action) => {
    setMutating(true);
    try {
      await api.post(`/api/tasks/${encodeURIComponent(decodedTaskId)}/${action}`);
      await Promise.all([loadTask({ quiet: true }), refreshTasks({ quiet: true })]);
    } finally {
      setMutating(false);
    }
  };

  const openOutputPath = async (outputPath) => {
    try {
      setActionError('');
      await api.post('/api/system/open_folder', { path: outputPath });
    } catch (openError) {
      setActionError(
        openError.response?.data?.detail
        || openError.message
        || t('error_cannot_open_folder'),
      );
    }
  };

  if (loading) {
    return <Group justify="center" h="100%"><Loader /></Group>;
  }

  if (error || !task) {
    return (
      <Box className={styles.page}>
        <Alert color="red" title={t('task_detail.load_error')} icon={<IconAlertTriangle size={18} />}>
          <Stack gap="sm">
            <Text>{error || t('task_detail.not_available')}</Text>
            <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={() => loadTask()}>
              {t('button_refresh')}
            </Button>
          </Stack>
        </Alert>
      </Box>
    );
  }

  return (
    <Box className={styles.page}>
      <Box className={styles.content}>
        <Group id="task-detail-header" justify="space-between" align="flex-start" gap="md" className={styles.header}>
          <Stack gap={6}>
            <Text size="sm" fw={700} c="dimmed" tt="uppercase">{t('task_detail.eyebrow')}</Text>
            <Group gap="sm" align="center">
              <Title order={1}>{kindLabel}</Title>
              <Badge color={displayStatusColor} variant="light" size="lg" className={styles.statusBadge}>
                {displayStatusLabel}
              </Badge>
              {task.archived_at && <Badge color="gray" variant="outline">{t('task_detail.archived')}</Badge>}
            </Group>
            <Text c="dimmed">{localizedTaskTitle}</Text>
          </Stack>
          <Group gap="sm">
            <Group gap={7} className={styles.timer} aria-label={t('task_detail.elapsed')}>
              <IconClock size={18} />
              <Text fw={700}>{duration}</Text>
            </Group>
            <Button variant="light" leftSection={<IconHistory size={17} />} onClick={openTaskCenter}>
              {t('task_center.title')}
            </Button>
            {(task.archived_at || task.allowed_actions?.includes('archive_task')) && (
              <Menu position="bottom-end" withinPortal>
                <Menu.Target>
                  <Button variant="subtle" px="sm" aria-label={t('task_detail.more_actions')}>
                    <IconDots size={19} />
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  {task.archived_at ? (
                  <Menu.Item leftSection={<IconRestore size={16} />} disabled={mutating} onClick={() => mutateArchive('restore')}>
                    {t('task_detail.restore')}
                  </Menu.Item>
                  ) : (
                  <Menu.Item leftSection={<IconArchive size={16} />} disabled={mutating} onClick={() => mutateArchive('archive')}>
                    {t('task_detail.archive')}
                  </Menu.Item>
                  )}
                </Menu.Dropdown>
              </Menu>
            )}
          </Group>
        </Group>

        {!isPartialGlossaryHealth && (task.attention_reason || ['failed', 'interrupted'].includes(task.status)) && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="md">
            {localizedNextStep}
          </Alert>
        )}
        {actionError && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="md" withCloseButton onClose={() => setActionError('')}>
            {actionError}
          </Alert>
        )}
        {task.blocking && active && (
          <Alert color="orange" icon={<IconInfoCircle size={18} />} mb="md">
            {localizedBlockingReason}
          </Alert>
        )}

        <Progress value={task.progress || 0} size="sm" radius="xl" mb="md" aria-label={t('task_center.progress')} />

        <Grid gutter="md" align="start">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Card id="task-detail-summary" withBorder radius="md" p="lg" mb="md" data-remis-surface="surface">
              <Title order={3} mb="md">{t('task_detail.user_summary')}</Title>
              <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
                <Box>
                  <Text size="xs" c="dimmed">{t('task_detail.current_stage')}</Text>
                  <Text fw={700}>{localizedTaskStage || displayStatusLabel}</Text>
                </Box>
                <Box>
                  <Text size="xs" c="dimmed">{t('task_detail.result')}</Text>
                  <Text>
                    {isGlossaryHealthResult
                      ? t('task_detail.detailed_result_below')
                      : (localizedResultSummary || displayStatusLabel)}
                  </Text>
                </Box>
                <Box>
                  <Text size="xs" c="dimmed">{t('task_detail.next_step')}</Text>
                  <Text>{localizedNextStep}</Text>
                </Box>
              </SimpleGrid>
            </Card>

            <details
              id="task-detail-technical-log"
              className={styles.technicalLogDetails}
              data-testid="task-event-log"
              open={logExpanded}
              onToggle={(event) => setLogExpanded(event.currentTarget.open)}
            >
              <summary>
                {t('task_detail.technical_logs')} · {t('task_detail.newest_first')}
              </summary>
              <Card withBorder radius="md" p="lg" className={styles.logCard} data-remis-surface="surface">
              <Group justify="space-between" mb="md">
                <div>
                  <Title order={3}>{t('task_detail.run_log')}</Title>
                  <Text size="sm" c="dimmed">
                    {active ? t('task_detail.live_updates') : t('task_detail.event_count', { count: task.events?.length || 0 })}
                  </Text>
                </div>
                <Group gap="xs">
                  <Button
                    component="a"
                    href={`/api/tasks/${encodeURIComponent(decodedTaskId)}/events/export?include_diagnostics=true`}
                    download
                    variant="subtle"
                    size="compact-sm"
                    leftSection={<IconDownload size={15} />}
                  >
                    {t('task_detail.export_log')}
                  </Button>
                  <Button variant="subtle" size="compact-sm" leftSection={<IconRefresh size={15} />} onClick={() => loadTask({ quiet: true })}>
                    {t('button_refresh')}
                  </Button>
                </Group>
              </Group>
              <ScrollArea.Autosize mah={620} type="auto" offsetScrollbars>
                {visibleEvents.length ? (
                  <Stack gap={0} className={styles.eventList}>
                    {visibleEvents.map(({ event, message, technical }) => (
                      <Box key={event.event_id} className={styles.eventRow} data-level={event.level}>
                        <Text size="xs" c="dimmed" className={styles.eventTime}>
                          {formatTimestamp(event.timestamp, i18n.language)}
                        </Text>
                        <Box className={styles.eventMarker} data-color={EVENT_COLORS[event.level] || 'gray'} />
                        <Group gap="xs" wrap="nowrap">
                          {technical && (
                            <Badge size="xs" color="gray" variant="outline">
                              {t('task_detail.diagnostic')}
                            </Badge>
                          )}
                          <Text size="sm" className={styles.eventMessage}>
                            {message}
                          </Text>
                        </Group>
                      </Box>
                    ))}
                  </Stack>
                ) : (
                  <Stack align="center" justify="center" h="100%" gap="xs">
                    <IconHistory size={28} opacity={0.55} />
                    <Text c="dimmed">{t('task_detail.no_events')}</Text>
                  </Stack>
                )}
              </ScrollArea.Autosize>
              </Card>
            </details>
          </Grid.Col>

          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap="md">
              <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                <Title order={3} mb="md">{t('task_detail.task_info')}</Title>
                <Stack gap="sm">
                  <Box>
                    <Group justify="space-between" align="flex-start" gap="sm" wrap="nowrap">
                      <Box className={styles.projectIdentityCopy}>
                        <Text size="xs" c="dimmed">{t('task_detail.project_name')}</Text>
                        <Text size="sm" fw={700} className={styles.projectName}>
                          {projectName || t('task_detail.not_available')}
                        </Text>
                      </Box>
                      {task.project_id && (
                        <Tooltip label={t('context_sidebar.project_details')} withArrow>
                          <ActionIcon
                            variant="subtle"
                            size="lg"
                            aria-label={`${t('context_sidebar.project_details')}: ${projectName || task.project_id}`}
                            onClick={() => navigate(`/project-management/${encodeURIComponent(task.project_id)}`)}
                          >
                            <IconArrowUpRight size={18} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Group>
                    {gameName && (
                      <Group gap="xs" mt="xs">
                        <Text size="xs" c="dimmed">{t('glossary_game')}</Text>
                        <Badge
                          color={getGameBadgeColor(gameId)}
                          data-game-color={getGameBadgeColor(gameId)}
                          variant="light"
                          size="sm"
                        >
                          {gameName}
                        </Badge>
                      </Group>
                    )}
                  </Box>
                  <Box>
                    <Text size="xs" c="dimmed">{t('task_detail.task_flow')}</Text>
                    <Text size="sm" fw={700}>{kindLabel}</Text>
                  </Box>
                  <Box><Text size="xs" c="dimmed">{t('task_center.created_by', { creator: creatorLabel })}</Text></Box>
                  <Divider />
                  <Group justify="space-between"><Text size="sm" c="dimmed">{t('task_detail.started_at')}</Text><Text size="sm">{formatTimestamp(task.started_at || task.created_at, i18n.language)}</Text></Group>
                  <Group justify="space-between"><Text size="sm" c="dimmed">{t('task_detail.finished_at')}</Text><Text size="sm">{formatTimestamp(task.finished_at, i18n.language)}</Text></Group>
                  {task.blocking && active && (
                    <Tooltip label={t('task_detail.blocking_description')} multiline maw={320} withArrow>
                      <Badge color="orange" variant="outline" leftSection={<IconInfoCircle size={13} />} className={styles.blockingBadge}>
                        {t('task_center.blocking')}
                      </Badge>
                    </Tooltip>
                  )}
                  <details className={styles.technicalDetails}>
                    <summary>{t('task_detail.technical_info')}</summary>
                    <Stack gap="xs" mt="xs">
                      <Box><Text size="xs" c="dimmed">{t('task_detail.task_id')}</Text><Code className={styles.taskId}>{task.task_id}</Code></Box>
                      <Box><Text size="xs" c="dimmed">{t('task_detail.project_id')}</Text><Code className={styles.taskId}>{task.project_id || t('task_detail.not_available')}</Code></Box>
                    </Stack>
                  </details>
                </Stack>
              </Card>

              {(task.result?.summary || task.result?.output_paths?.length > 0 || isGlossaryHealthResult || isGlossaryMergeResult) && (
                <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                  <Title order={3} mb="sm">{t('task_detail.result')}</Title>
                  {localizedResultSummary && <Text size="sm" mb="sm">{localizedResultSummary}</Text>}
                  {workshopRepairResults.length > 0 && (
                    <Stack gap="xs" mb="sm" data-testid="workshop-repair-results">
                      <Text size="xs" fw={700} c="dimmed">
                        {t('task_detail.repair_item_results')}
                      </Text>
                      {workshopRepairResults.map((item, index) => {
                        const repaired = item.status === 'SUCCESS';
                        return (
                          <Paper
                            key={`${item.file_name}:${item.key}:${index}`}
                            withBorder
                            p="sm"
                            className={styles.repairResultItem}
                            data-remis-surface="paper"
                          >
                            <Group justify="space-between" align="flex-start" wrap="nowrap" gap="sm">
                              <Box style={{ minWidth: 0 }}>
                                <Text size="xs" c="dimmed" className={styles.repairResultFile}>{item.file_name}</Text>
                                <Code className={styles.repairResultKey}>{item.key}</Code>
                              </Box>
                              <Badge color={repaired ? 'green' : 'orange'} variant="outline" className={styles.repairResultBadge}>
                                {t(repaired
                                  ? 'task_detail.repair_item_fixed'
                                  : 'task_detail.repair_item_needs_review')}
                              </Badge>
                            </Group>
                            {!repaired && item.parity_message && (
                              <Text size="xs" mt="xs" className={styles.repairResultReason}>
                                {t('task_detail.repair_item_reason')}: {item.parity_message}
                              </Text>
                            )}
                          </Paper>
                        );
                      })}
                    </Stack>
                  )}
                  {isGlossaryHealthResult && (
                    <Stack gap="sm" mb="sm" data-testid="glossary-health-task-result">
                      <Group gap="xs">
                        <Badge color={resultMetadata.score >= 80 ? 'teal' : resultMetadata.score >= 60 ? 'orange' : 'red'}>
                          {t('glossary_health_score', 'Score')} {resultMetadata.score}/100
                        </Badge>
                        <Badge variant="light">
                          {resultMetadata.issue_count || 0} {t('glossary_health_issues', 'issues')}
                        </Badge>
                        {resultMetadata.mutations_applied === false && (
                          <Badge color="teal" variant="outline">
                            {t('glossary_health_read_only', 'Read-only')}
                          </Badge>
                        )}
                      </Group>
                      <GlossaryHealthPenaltyBreakdown issues={resultMetadata.issues} />
                      {(resultMetadata.issues || []).map((issue) => (
                        <Box key={issue.code}>
                          <Group justify="space-between" gap="xs" wrap="nowrap">
                            <Text size="sm" fw={700}>
                              {t(`glossary_health_issue_${issue.code}`, {
                                defaultValue: issue.message || issue.code,
                              })}
                            </Text>
                            <Badge color={issue.severity === 'error' ? 'red' : issue.severity === 'warning' ? 'orange' : 'blue'}>
                              {issue.count}
                            </Badge>
                          </Group>
                        </Box>
                      ))}
                      {hasGlossaryHealthCases && (
                        <Button
                          color="teal"
                          variant="light"
                          leftSection={<IconTool size={17} />}
                          onClick={() => navigate(glossaryHealthReviewRoute(task.task_id))}
                        >
                          {t('glossary_health_workbench', { defaultValue: 'Review and fix issues' })}
                        </Button>
                      )}
                      {resultMetadata.ai_review_status === 'failed' && (
                        <Alert color="orange" icon={<IconAlertTriangle size={16} />}>
                          <Stack gap="xs">
                            <Text size="sm">{t('glossary_health_partial_message')}</Text>
                            <details className={styles.technicalDetails}>
                              <summary>{t('task_detail.technical_info')}</summary>
                              <Code block mt="xs">
                                {resultMetadata.ai_review_error || task.message || t('task_detail.not_available')}
                              </Code>
                            </details>
                          </Stack>
                        </Alert>
                      )}
                    </Stack>
                  )}
                  {isGlossaryMergeResult && (
                    <Stack gap="xs" mb="sm" data-testid="glossary-merge-task-result">
                      <Group gap="xs" wrap="wrap">
                        <Badge color="gray">
                          {resultMetadata.duplicate_term_count || 0} {t('glossary_merge_duplicates', 'duplicates')}
                        </Badge>
                        <Badge color={resultMetadata.conflict_count ? 'orange' : 'teal'}>
                          {resultMetadata.conflict_count || 0} {t('glossary_merge_conflicts', 'conflicts')}
                        </Badge>
                        {resultMetadata.skipped_conflict_count > 0 && (
                          <Badge color="orange" variant="outline">
                            {resultMetadata.skipped_conflict_count} {t('glossary_merge_skip_conflicts', 'skipped conflicts')}
                          </Badge>
                        )}
                      </Group>
                      {(resultMetadata.merged_from || []).map((source) => (
                        <Text key={source.glossary_id} size="xs" c="dimmed">
                          {source.name} · {source.game_id}
                        </Text>
                      ))}
                    </Stack>
                  )}
                  {task.result.output_paths?.length > 0 && (
                    <Stack gap={6}>
                      <Text size="xs" c="dimmed">{t('task_detail.output_paths')}</Text>
                      {task.result.output_paths.map((outputPath) => (
                        <Group key={outputPath} gap="xs" wrap="nowrap">
                          <Code style={{ flex: 1, overflowWrap: 'anywhere' }}>{outputPath}</Code>
                          <ActionIcon
                            variant="light"
                            aria-label={`${t('button_open_folder')}: ${outputPath}`}
                            onClick={() => openOutputPath(outputPath)}
                          >
                            <IconFolderOpen size={17} />
                          </ActionIcon>
                        </Group>
                      ))}
                    </Stack>
                  )}
                  {task.kind === 'incremental_translation' && task.status === 'completed' && task.project_id && (
                    <Button
                      mt="sm"
                      variant="light"
                      leftSection={<IconCheck size={17} />}
                      onClick={() => navigate(buildProofreadingUrl({
                        projectId: task.project_id,
                        taskId: task.task_id,
                      }))}
                    >
                      {t('project_management.primary_continue_proofreading')}
                    </Button>
                  )}
                </Card>
              )}

              {task.checkpoint?.available && (
                <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                  <Group justify="space-between" mb="xs">
                    <Title order={3}>
                      {t('incremental_translation.checkpoint_found_label', { defaultValue: 'Recovery checkpoint' })}
                    </Title>
                    <Badge color={task.checkpoint.resume_supported ? 'teal' : 'gray'} variant="light">
                      {task.checkpoint.resume_supported
                        ? t('incremental_translation.resume_enabled', { defaultValue: 'Resume available' })
                        : t('task_detail.not_available')}
                    </Badge>
                  </Group>
                  <Text size="sm" fw={700}>
                    {task.checkpoint.stage && !/^(failed|translating)$/i.test(task.checkpoint.stage)
                      ? task.checkpoint.stage
                      : localizedTaskStage}
                  </Text>
                  {task.checkpoint.updated_at && (
                    <Text size="xs" c="dimmed">
                      {formatTimestamp(task.checkpoint.updated_at, i18n.language)}
                    </Text>
                  )}
                </Card>
              )}

              {task.children?.length > 0 && (
                <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                  <Group justify="space-between" mb="xs">
                    <Title order={3}>{t('task_detail.child_tasks')}</Title>
                    <Badge variant="light">
                      {task.child_aggregate?.completed || 0}/{task.child_aggregate?.total || task.children.length}
                    </Badge>
                  </Group>
                  <Progress value={task.child_aggregate?.progress || 0} size="xs" mb="sm" />
                  <Group gap="xs" mb="sm">
                    {task.child_aggregate?.active > 0 && (
                      <Badge color="blue" variant="outline">
                        {t('task_center.status.running')} {task.child_aggregate.active}
                      </Badge>
                    )}
                    {task.child_aggregate?.attention > 0 && (
                      <Badge color="orange" variant="outline">
                        {t('task_center.attention_summary', { count: task.child_aggregate.attention })}
                      </Badge>
                    )}
                  </Group>
                  <Stack gap="xs">
                    {task.children.map((child) => (
                      <Button key={child.task_id} variant="subtle" justify="space-between" onClick={() => navigate(taskDetailRoute(child.task_id))}>
                        {t(`task_center.kind.${child.kind}`, { defaultValue: child.title })}
                        <Badge color={STATUS_COLORS[child.status] || 'gray'} variant="light">{t(`task_center.status.${child.status}`)}</Badge>
                      </Button>
                    ))}
                  </Stack>
                </Card>
              )}

              <Button
                variant="light"
                leftSection={active ? <IconPlayerPlay size={17} /> : <IconArrowBackUp size={17} />}
                onClick={() => {
                  const target = taskWorkflowTarget(task);
                  navigate(target.pathname, { state: target.state });
                }}
              >
                {t('task_detail.back_to_workflow')}
              </Button>
            </Stack>
          </Grid.Col>
        </Grid>
      </Box>
    </Box>
  );
}
