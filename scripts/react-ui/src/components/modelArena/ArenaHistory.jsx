import React from 'react';
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconEye, IconFileExport, IconHistory, IconTrash } from '@tabler/icons-react';
import { formatCurrentLocalizedDateTime } from '../../utils/localizedDateTime';

const statusColor = {
  draft: 'gray',
  queued: 'blue',
  running: 'blue',
  voting: 'violet',
  completed: 'green',
  partial_failed: 'yellow',
  failed: 'red',
  abandoned: 'gray',
};

export default function ArenaHistory({
  t,
  runs,
  projects,
  loading,
  onOpen,
  onPreviewExport,
  onDelete,
}) {
  const activeProjectIds = new Set((projects || []).map(
    (project) => String(project.project_id || project.value || ''),
  ));
  return (
    <Stack gap="lg">
      <div>
        <Title order={3}>{t('model_arena.history_title')}</Title>
        <Text c="dimmed">{t('model_arena.history_description')}</Text>
      </div>
      {loading ? (
        <Group justify="center" py={80}><Loader /></Group>
      ) : runs.length === 0 ? (
        <Card data-remis-surface="paper" withBorder radius="md" padding="xl">
          <Stack align="center" py="xl">
            <IconHistory size={34} opacity={0.5} />
            <Text fw={700}>{t('model_arena.history_empty')}</Text>
            <Text size="sm" c="dimmed">{t('model_arena.history_empty_description')}</Text>
          </Stack>
        </Card>
      ) : runs.map((run) => {
        const projectDeleted = Boolean(
          run.project_id && !activeProjectIds.has(String(run.project_id)),
        );
        return (
        <Card
          key={run.run_id}
          data-remis-surface="paper"
          withBorder
          radius="md"
          padding="lg"
        >
          <Group justify="space-between" align="center">
            <div>
              <Group gap="xs">
                <Text fw={700}>{run.project_name_snapshot || run.project_name || t('model_arena.deleted_project')}</Text>
                <Badge color={statusColor[run.status] || 'gray'}>
                  {t(`model_arena.status_${run.status}`, { defaultValue: run.status })}
                </Badge>
                {projectDeleted && (
                  <Badge color="gray" variant="outline">
                    {t('model_arena.project_deleted')}
                  </Badge>
                )}
              </Group>
              <Text size="sm" c="dimmed">
                {run.source_lang_code} → {run.target_lang_code}
                {' · '}
                {t('model_arena.sample_count_value', { count: run.sample_size })}
                {' · '}
                {run.created_at ? formatCurrentLocalizedDateTime(run.created_at) : ''}
              </Text>
              {run.sample_seed && (
                <Text size="xs" c="dimmed">{t('model_arena.seed', { seed: run.sample_seed })}</Text>
              )}
            </div>
            <Group gap="xs">
              <Button
                variant="light"
                leftSection={<IconEye size={16} />}
                onClick={() => onOpen(run)}
              >
                {t('model_arena.open')}
              </Button>
              {['completed', 'partial_failed'].includes(run.status) && (
                <ActionIcon
                  variant="light"
                  size="lg"
                  aria-label={t('model_arena.export_preview')}
                  onClick={() => onPreviewExport(run)}
                >
                  <IconFileExport size={18} />
                </ActionIcon>
              )}
              <ActionIcon
                variant="subtle"
                color="red"
                size="lg"
                aria-label={t('model_arena.delete')}
                onClick={() => onDelete(run)}
              >
                <IconTrash size={18} />
              </ActionIcon>
            </Group>
          </Group>
        </Card>
        );
      })}
    </Stack>
  );
}
