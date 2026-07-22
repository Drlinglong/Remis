import React from 'react';
import { Alert, Button, Drawer, Group, Loader, ScrollArea, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useTaskCenter } from '../../context/TaskCenterContextCore';
import { TaskSummaryCard } from './TaskSummaryCard';

export function TaskCenterDrawer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    attentionCount,
    closeTaskCenter,
    loading,
    opened,
    refreshTasks,
    tasks,
  } = useTaskCenter();

  const openTask = (task) => {
    closeTaskCenter();
    navigate(task.source_route || '/');
  };

  return (
    <Drawer
      opened={opened}
      onClose={closeTaskCenter}
      position="right"
      size="min(460px, 92vw)"
      title={<Text component="span" fw={700} size="lg">{t('task_center.title')}</Text>}
      overlayProps={{ backgroundOpacity: 0.58, blur: 2 }}
      styles={{ content: { background: 'var(--elevated-bg, var(--surface-bg))', color: 'var(--surface-text-main)' } }}
    >
      <Stack h="calc(100vh - 90px)" gap="md" data-remis-surface="elevated">
        <Group justify="space-between">
          <Text size="sm" c="dimmed">{t('task_center.subtitle')}</Text>
          <Button
            variant="subtle"
            size="compact-sm"
            leftSection={<IconRefresh size={15} />}
            onClick={() => refreshTasks()}
          >
            {t('button_refresh')}
          </Button>
        </Group>
        {attentionCount > 0 && (
          <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
            {t('task_center.attention_summary', { count: attentionCount })}
          </Alert>
        )}
        <ScrollArea style={{ flex: 1 }} type="auto">
          {loading ? (
            <Group justify="center" py="xl"><Loader size="sm" /></Group>
          ) : tasks.length > 0 ? (
            <Stack gap="sm" pr="xs">
              {tasks.map((task) => (
                <TaskSummaryCard key={task.task_id} task={task} onOpen={openTask} />
              ))}
            </Stack>
          ) : (
            <Stack align="center" py="xl" gap="xs">
              <Text fw={700}>{t('task_center.empty_title')}</Text>
              <Text size="sm" c="dimmed" ta="center">{t('task_center.empty_description')}</Text>
            </Stack>
          )}
        </ScrollArea>
      </Stack>
    </Drawer>
  );
}
