import React from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Progress,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconClock, IconRefresh } from '@tabler/icons-react';

export default function ArenaRunStatus({ t, run, onRefresh, onRetryFailures, retrying }) {
  const progress = Number(run.progress?.percent ?? run.progress_percent ?? 0);
  const completed = Number(run.progress?.completed ?? run.completed_requests ?? 0);
  const total = Number(run.progress?.total ?? run.estimated_request_count ?? 0);
  const hasFailure = ['partial_failed', 'failed'].includes(run.status);

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={3}>{t('model_arena.running_title')}</Title>
          <Text c="dimmed">{t('model_arena.running_description')}</Text>
        </div>
        <Badge color={hasFailure ? 'yellow' : 'blue'} variant="light" size="lg">
          {t(`model_arena.status_${run.status}`, { defaultValue: run.status })}
        </Badge>
      </Group>

      <Card data-remis-surface="paper" withBorder radius="md" padding="xl">
        <Stack align="center" gap="lg">
          {!hasFailure && <Loader type="dots" />}
          <div style={{ width: '100%' }}>
            <Group justify="space-between" mb="xs">
              <Text fw={700}>{run.progress?.stage_label || t('model_arena.translating_samples')}</Text>
              <Text size="sm" c="dimmed">{total ? `${completed}/${total}` : `${Math.round(progress)}%`}</Text>
            </Group>
            <Progress value={progress} animated={!hasFailure} />
          </div>
          <Group gap="xs">
            <IconClock size={16} />
            <Text size="sm" c="dimmed">{t('model_arena.background_notice')}</Text>
          </Group>
        </Stack>
      </Card>

      {hasFailure && (
        <Alert
          color="yellow"
          icon={<IconAlertTriangle size={18} />}
          title={t('model_arena.partial_failed')}
        >
          <Stack>
            <Text size="sm">{t('model_arena.partial_failed_description')}</Text>
            <Group>
              <Button
                variant="light"
                color="yellow"
                leftSection={<IconRefresh size={16} />}
                onClick={onRetryFailures}
                loading={retrying}
              >
                {t('model_arena.retry_failures')}
              </Button>
              <Button variant="subtle" onClick={onRefresh}>{t('button_refresh')}</Button>
            </Group>
          </Stack>
        </Alert>
      )}
    </Stack>
  );
}
