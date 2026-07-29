import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCalendar,
  IconChevronLeft,
  IconChevronRight,
  IconClock,
  IconHistory,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import api from '../utils/api';
import { taskDayBounds } from '../utils/taskDates';
import { taskDetailRoute } from '../utils/taskRoutes';
import { formatTaskDuration, taskDurationMs } from '../utils/taskTime';
import styles from './TaskHistoryPage.module.css';

const PAGE_SIZE = 100;
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

const toDateInput = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const shiftDate = (dateInput, amount) => {
  const date = new Date(`${dateInput}T12:00:00`);
  date.setDate(date.getDate() + amount);
  return toDateInput(date);
};

const formatTaskTime = (task, locale) => {
  const value = task.created_at || task.started_at;
  if (!value) return '--:--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

export default function TaskHistoryPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const today = useMemo(() => toDateInput(new Date()), []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [tasks, setTasks] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const loadTasks = useCallback(async (offset = 0, append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const { fromTime, toTime } = taskDayBounds(selectedDate);
      const response = await api.get('/api/tasks', {
        params: {
          include_archived: true,
          from_time: fromTime,
          to_time: toTime,
          offset,
          limit: PAGE_SIZE,
        },
      });
      const nextTasks = Array.isArray(response.data?.tasks) ? response.data.tasks : [];
      setTasks((current) => (append ? [...current, ...nextTasks] : nextTasks));
      setTotalCount(Number(response.data?.total_count || 0));
      setError('');
    } catch (loadError) {
      setError(loadError.response?.data?.detail || loadError.message || t('task_history.load_error'));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [selectedDate, t]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  return (
    <Box className={styles.page}>
      <Box className={styles.content}>
        <Group justify="space-between" align="flex-end" gap="md" mb="xl">
          <div>
            <Text size="sm" fw={700} c="dimmed" tt="uppercase">{t('task_history.eyebrow')}</Text>
            <Title order={1}>{t('task_history.title')}</Title>
            <Text c="dimmed" maw={720}>{t('task_history.subtitle')}</Text>
          </div>
          <Group gap="xs" wrap="nowrap" className={styles.dateControls}>
            <ActionIcon variant="light" size="lg" aria-label={t('task_history.previous_day')} onClick={() => setSelectedDate(shiftDate(selectedDate, -1))}>
              <IconChevronLeft size={18} />
            </ActionIcon>
            <TextInput
              type="date"
              value={selectedDate}
              onChange={(event) => {
                if (event.currentTarget.value) setSelectedDate(event.currentTarget.value);
              }}
              leftSection={<IconCalendar size={16} />}
              aria-label={t('task_history.select_day')}
            />
            <ActionIcon variant="light" size="lg" aria-label={t('task_history.next_day')} onClick={() => setSelectedDate(shiftDate(selectedDate, 1))}>
              <IconChevronRight size={18} />
            </ActionIcon>
            <Button variant="subtle" disabled={selectedDate === today} onClick={() => setSelectedDate(today)}>
              {t('task_history.today')}
            </Button>
          </Group>
        </Group>

        <Group justify="space-between" mb="sm">
          <Title order={3}>{t('task_history.day_heading', { date: selectedDate })}</Title>
          <Text size="sm" c="dimmed">{t('task_history.task_count', { count: totalCount })}</Text>
        </Group>

        {error && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="md">
            <Group justify="space-between">
              <Text>{error}</Text>
              <Button variant="subtle" color="red" onClick={() => loadTasks()}>{t('button_refresh')}</Button>
            </Group>
          </Alert>
        )}

        {loading ? (
          <Group justify="center" py={80}><Loader /></Group>
        ) : tasks.length === 0 ? (
          <Card withBorder radius="md" p="xl" data-remis-surface="surface">
            <Stack align="center" gap="xs" py="xl">
              <IconHistory size={32} opacity={0.5} />
              <Text fw={700}>{t('task_history.empty_title')}</Text>
              <Text size="sm" c="dimmed">{t('task_history.empty_description')}</Text>
            </Stack>
          </Card>
        ) : (
          <Stack gap="sm">
            {tasks.map((task) => {
              const kindLabel = t(`task_center.kind.${task.kind}`, { defaultValue: task.title });
              const creatorLabel = task.created_by?.label || t(`task_center.creator.${task.created_by?.type || 'system'}`);
              const projectGameId = task.project_context?.game_id;
              const projectGameName = projectGameId
                ? t(`game_name_${String(projectGameId).toLowerCase()}`, { defaultValue: projectGameId })
                : '';
              const projectLabel = [task.project_context?.name, projectGameName].filter(Boolean).join(' — ');
              const resultMetadata = task.result?.metadata || {};
              const healthMetadata = resultMetadata.preview || resultMetadata;
              const isModelArenaTask = ['model_arena', 'model_arena_retry'].includes(task.kind);
              const secondaryLabel = projectLabel || (
                task.kind === 'glossary_health_check'
                  ? t('glossary_health_task_title', {
                    count: healthMetadata.glossary_count || 1,
                    defaultValue: task.title,
                  })
                  : (isModelArenaTask ? null : task.title)
              );
              return (
                <Card
                  key={task.task_id}
                  component="button"
                  type="button"
                  withBorder
                  radius="md"
                  p="md"
                  data-remis-surface="surface"
                  className={styles.taskRow}
                  aria-label={kindLabel}
                  onClick={() => navigate(taskDetailRoute(task.task_id))}
                >
                  <Group justify="space-between" align="center" wrap="nowrap">
                    <Group gap="md" wrap="nowrap" className={styles.taskMain}>
                      <Text size="sm" c="dimmed" ff="monospace" className={styles.taskTime}>
                        {formatTaskTime(task, i18n.language)}
                      </Text>
                      <div className={styles.taskIdentity}>
                        <Text fw={700} className={styles.taskTitle}>{kindLabel}</Text>
                        {secondaryLabel && (
                          <Text size="sm" c="dimmed" lineClamp={1}>{secondaryLabel}</Text>
                        )}
                      </div>
                    </Group>
                    <Group gap="sm" wrap="nowrap">
                      <Text size="xs" c="dimmed" visibleFrom="sm">{creatorLabel}</Text>
                      <Group gap={5} c="dimmed" wrap="nowrap" visibleFrom="sm">
                        <IconClock size={14} />
                        <Text size="xs" ff="monospace">{formatTaskDuration(taskDurationMs(task))}</Text>
                      </Group>
                      {task.archived_at && <Badge color="gray" variant="outline">{t('task_history.handled')}</Badge>}
                      <Badge color={STATUS_COLORS[task.status] || 'gray'} variant="light">
                        {t(`task_center.status.${task.status}`, { defaultValue: task.status })}
                      </Badge>
                    </Group>
                  </Group>
                </Card>
              );
            })}
            {tasks.length < totalCount && (
              <Button variant="light" loading={loadingMore} onClick={() => loadTasks(tasks.length, true)}>
                {t('task_history.load_more')}
              </Button>
            )}
          </Stack>
        )}
      </Box>
    </Box>
  );
}
