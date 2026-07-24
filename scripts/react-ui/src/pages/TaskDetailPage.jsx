import React, { useCallback, useEffect, useState } from 'react';
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
  Progress,
  ScrollArea,
  Stack,
  Switch,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArchive,
  IconArrowUpRight,
  IconArrowBackUp,
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
import { useNavigate, useParams } from 'react-router-dom';

import { useTaskCenter } from '../context/TaskCenterContextCore';
import api from '../utils/api';
import { getGameBadgeColor } from '../utils/gamePresentation';
import { ACTIVE_TASK_STATUSES, formatTaskDuration, taskDurationMs } from '../utils/taskTime';
import { glossaryHealthReviewRoute, taskDetailRoute } from '../utils/taskRoutes';
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

const workflowRoute = (sourceRoute) => (
  sourceRoute === '/glossary' ? '/glossary-manager' : (sourceRoute || '/')
);

const formatTimestamp = (value, locale) => {
  if (!value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(locale);
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
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mutating, setMutating] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [actionError, setActionError] = useState('');

  const loadTask = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const response = await api.get(`/api/tasks/${encodeURIComponent(decodedTaskId)}`, {
        params: { include_diagnostics: showDiagnostics },
      });
      setTask(response.data);
      setError('');
    } catch (loadError) {
      setError(loadError.response?.data?.detail || loadError.message || t('task_detail.load_error'));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [decodedTaskId, showDiagnostics, t]);

  useEffect(() => {
    loadTask();
  }, [loadTask]);

  const taskStatus = task?.status;

  useEffect(() => {
    if (!ACTIVE_TASK_STATUSES.has(taskStatus)) return undefined;
    let socket;
    let retryTimer;
    let refreshTimer;
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
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (refreshTimer) window.clearTimeout(refreshTimer);
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
  const healthMetadata = resultMetadata.preview || resultMetadata;
  const resultTypes = new Set(task?.result?.types || []);
  const isGlossaryHealthResult = resultTypes.has('glossary_health_report');
  const isGlossaryMergeResult = resultTypes.has('glossary_merge');
  const localizedTaskTitle = task?.kind === 'glossary_health_check'
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
    : task?.result?.summary;
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
        <Group justify="space-between" align="flex-start" gap="md" className={styles.header}>
          <Stack gap={6}>
            <Text size="sm" fw={700} c="dimmed" tt="uppercase">{t('task_detail.eyebrow')}</Text>
            <Group gap="sm" align="center">
              <Title order={1}>{kindLabel}</Title>
              <Badge color={STATUS_COLORS[task.status] || 'gray'} variant="light" size="lg">
                {statusLabel}
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

        {(task.attention_reason || ['failed', 'interrupted'].includes(task.status)) && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="md">
            {task.attention_reason || task.message || t('task_center.status.failed')}
          </Alert>
        )}
        {actionError && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="md" withCloseButton onClose={() => setActionError('')}>
            {actionError}
          </Alert>
        )}
        {task.blocking && active && (
          <Alert color="orange" icon={<IconInfoCircle size={18} />} mb="md">
            {task.blocking_reason || t('task_detail.blocking_description')}
          </Alert>
        )}

        <Progress value={task.progress || 0} size="sm" radius="xl" mb="md" aria-label={t('task_center.progress')} />

        <Grid gutter="md" align="stretch">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Card withBorder radius="md" p="lg" className={styles.logCard} data-remis-surface="surface">
              <Group justify="space-between" mb="md">
                <div>
                  <Title order={3}>{t('task_detail.run_log')}</Title>
                  <Text size="sm" c="dimmed">
                    {active ? t('task_detail.live_updates') : t('task_detail.event_count', { count: task.events?.length || 0 })}
                  </Text>
                </div>
                <Group gap="xs">
                  <Switch
                    size="sm"
                    checked={showDiagnostics}
                    onChange={(event) => setShowDiagnostics(event.currentTarget.checked)}
                    label={t('task_detail.show_diagnostics')}
                    aria-label={t('task_detail.show_diagnostics')}
                  />
                  <Button
                    component="a"
                    href={`/api/tasks/${encodeURIComponent(decodedTaskId)}/events/export?include_diagnostics=${showDiagnostics}`}
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
              <ScrollArea h="min(58vh, 620px)" type="auto" offsetScrollbars>
                {task.events?.length ? (
                  <Stack gap={0} className={styles.eventList}>
                    {task.events.map((event) => (
                      <Box key={event.event_id} className={styles.eventRow} data-level={event.level}>
                        <Text size="xs" c="dimmed" className={styles.eventTime}>
                          {formatTimestamp(event.timestamp, i18n.language)}
                        </Text>
                        <Box className={styles.eventMarker} data-color={EVENT_COLORS[event.level] || 'gray'} />
                        <Group gap="xs" wrap="nowrap">
                          {event.audience === 'diagnostic' && (
                            <Badge size="xs" color="gray" variant="outline">
                              {t('task_detail.diagnostic')}
                            </Badge>
                          )}
                          <Text size="sm" className={styles.eventMessage}>{event.message}</Text>
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
              </ScrollArea>
            </Card>
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
                          {resultMetadata.ai_review_error || task.message}
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
                  <Text size="sm" fw={700}>{task.checkpoint.stage || task.stage}</Text>
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
                onClick={() => navigate(workflowRoute(task.source_route))}
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
