import React, { useEffect, useState } from 'react';
import { Badge, Button, Group, Paper, Progress, Stack, Text } from '@mantine/core';
import { IconArrowRight, IconClock } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { ACTIVE_TASK_STATUSES, formatTaskDuration, taskDurationMs } from '../../utils/taskTime';

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

export function TaskSummaryCard({ compact = false, handling = false, onHandle, onOpen, task }) {
  const { t } = useTranslation();
  const active = ACTIVE_TASK_STATUSES.has(task.status);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!active) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  const kindLabel = t(`task_center.kind.${task.kind}`, { defaultValue: task.title });
  const statusLabel = t(`task_center.status.${task.status}`, { defaultValue: task.status });
  const creatorLabel = task.created_by?.label || t(`task_center.creator.${task.created_by?.type || 'system'}`);
  const showProgress = ['queued', 'running'].includes(task.status);
  const rawDetail = task.stage || task.message;
  const localizedDetail = ['glossary_health_check', 'glossary_merge'].includes(task.kind)
    ? (
      task.kind === 'glossary_health_check' && task.status === 'failed'
        ? (
          /no models loaded/i.test(task.message || '')
            ? t('glossary_health_no_model_loaded')
            : t('glossary_health_model_request_failed')
        )
        : statusLabel
    )
    : rawDetail;

  return (
    <Paper withBorder radius="md" p={compact ? 'sm' : 'md'} data-remis-surface="surface">
      <Stack gap={compact ? 6 : 'sm'}>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div style={{ minWidth: 0 }}>
            <Text fw={700} lineClamp={1}>{kindLabel}</Text>
            {localizedDetail && (
              <Text size="sm" c="dimmed" lineClamp={compact ? 1 : 2}>
                {localizedDetail}
              </Text>
            )}
          </div>
          <Badge color={STATUS_COLORS[task.status] || 'gray'} variant="light">
            {statusLabel}
          </Badge>
        </Group>
        {showProgress && (
          <Progress value={task.progress || 0} size="sm" radius="xl" aria-label={t('task_center.progress')} />
        )}
        {task.attention_reason && (
          <Text size="sm" c="orange">{task.attention_reason}</Text>
        )}
        <Group gap="xs">
          <Text size="xs" c="dimmed">{t('task_center.created_by', { creator: creatorLabel })}</Text>
          {task.blocking && ['queued', 'running', 'awaiting_approval'].includes(task.status) && (
            <Badge size="xs" color="orange" variant="outline">{t('task_center.blocking')}</Badge>
          )}
        </Group>
        <Group justify="space-between">
          <Group gap={6} c="dimmed" title={t('task_detail.elapsed')}>
            <IconClock size={14} />
            <Text size="xs" ff="monospace">
              {formatTaskDuration(taskDurationMs(task, now))}
            </Text>
            {showProgress && <Text size="xs">· {task.progress || 0}%</Text>}
          </Group>
          <Group gap={4}>
            {onHandle && task.allowed_actions?.includes('archive_task') && (
              <Button
                variant="subtle"
                color="gray"
                size="compact-sm"
                loading={handling}
                onClick={() => onHandle(task)}
              >
                {t('task_center.mark_handled')}
              </Button>
            )}
            <Button
              variant="subtle"
              size="compact-sm"
              rightSection={<IconArrowRight size={14} />}
              onClick={() => onOpen(task)}
            >
              {t('task_center.view_task')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </Paper>
  );
}
