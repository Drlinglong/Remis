import React from 'react';
import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconPlayerPlay, IconRefresh } from '@tabler/icons-react';

export default function ResumeCheckpointModal({
  checkpointInfo,
  onClose,
  onResume,
  onStartOver,
  opened,
  t,
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Group><IconAlertCircle color="orange" /> <Text fw={700}>{t('translation_page.resume_modal.title')}</Text></Group>}
      centered
    >
      <Stack>
        <Text>
          {t('translation_page.resume_modal.content')}
        </Text>
        {checkpointInfo && (
          <Alert color="blue" variant="light">
            <Text size="sm"><b>{t('translation_page.resume_modal.completed_files')}</b> {checkpointInfo.completed_count}</Text>
            {checkpointInfo.total_files_estimate > 0 && (
              <Text size="sm"><b>{t('translation_page.resume_modal.estimated_progress')}</b> {Math.round((checkpointInfo.completed_count / checkpointInfo.total_files_estimate) * 100)}%</Text>
            )}
            {checkpointInfo.metadata?.model_name && (
              <Text size="sm"><b>{t('translation_page.resume_modal.previous_model')}</b> {checkpointInfo.metadata.model_name}</Text>
            )}
          </Alert>
        )}
        <Text size="sm" c="dimmed">
          {t('translation_page.resume_modal.question')}
        </Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={onStartOver} leftSection={<IconRefresh size={16} />}>
            {t('translation_page.resume_modal.start_over')}
          </Button>
          <Button onClick={onResume} leftSection={<IconPlayerPlay size={16} />}>
            {t('translation_page.resume_modal.resume')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
