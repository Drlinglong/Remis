import React, { useCallback, useEffect, useState } from 'react';
import {
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
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArchive,
  IconArrowBackUp,
  IconClock,
  IconDots,
  IconHistory,
  IconPlayerPlay,
  IconRefresh,
  IconRestore,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { useTaskCenter } from '../context/TaskCenterContextCore';
import api from '../utils/api';
import { ACTIVE_TASK_STATUSES, formatTaskDuration, taskDurationMs } from '../utils/taskTime';
import { taskDetailRoute } from '../utils/taskRoutes';
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

  const loadTask = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const response = await api.get(`/api/tasks/${encodeURIComponent(decodedTaskId)}`);
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

  const mutateArchive = async (action) => {
    setMutating(true);
    try {
      await api.post(`/api/tasks/${encodeURIComponent(decodedTaskId)}/${action}`);
      await Promise.all([loadTask({ quiet: true }), refreshTasks({ quiet: true })]);
    } finally {
      setMutating(false);
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
            <Text c="dimmed">{task.title}</Text>
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
                <Button variant="subtle" size="compact-sm" leftSection={<IconRefresh size={15} />} onClick={() => loadTask({ quiet: true })}>
                  {t('button_refresh')}
                </Button>
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
                        <Text size="sm" className={styles.eventMessage}>{event.message}</Text>
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
                  <Box><Text size="xs" c="dimmed">{t('task_detail.task_id')}</Text><Code className={styles.taskId}>{task.task_id}</Code></Box>
                  <Box><Text size="xs" c="dimmed">{t('task_detail.project')}</Text><Text size="sm">{task.project_id || t('task_detail.not_available')}</Text></Box>
                  <Box><Text size="xs" c="dimmed">{t('task_center.created_by', { creator: creatorLabel })}</Text></Box>
                  <Divider />
                  <Group justify="space-between"><Text size="sm" c="dimmed">{t('task_detail.started_at')}</Text><Text size="sm">{formatTimestamp(task.started_at || task.created_at, i18n.language)}</Text></Group>
                  <Group justify="space-between"><Text size="sm" c="dimmed">{t('task_detail.finished_at')}</Text><Text size="sm">{formatTimestamp(task.finished_at, i18n.language)}</Text></Group>
                  {task.blocking && <Badge color="orange" variant="outline">{t('task_center.blocking')}</Badge>}
                </Stack>
              </Card>

              {(task.result?.summary || task.result?.output_paths?.length > 0) && (
                <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                  <Title order={3} mb="sm">{t('task_detail.result')}</Title>
                  {task.result.summary && <Text size="sm" mb="sm">{task.result.summary}</Text>}
                  {task.result.output_paths?.length > 0 && (
                    <Stack gap={6}>
                      <Text size="xs" c="dimmed">{t('task_detail.output_paths')}</Text>
                      {task.result.output_paths.map((outputPath) => <Code key={outputPath}>{outputPath}</Code>)}
                    </Stack>
                  )}
                </Card>
              )}

              {task.children?.length > 0 && (
                <Card withBorder radius="md" p="lg" data-remis-surface="surface">
                  <Title order={3} mb="sm">{t('task_detail.child_tasks')}</Title>
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
                onClick={() => navigate(task.source_route || '/')}
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
