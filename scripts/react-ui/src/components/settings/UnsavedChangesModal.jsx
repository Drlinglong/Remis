import React from 'react';
import { Button, Group, Modal, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export default function UnsavedChangesModal({ opened, onReturn, onDiscard }) {
  const { t } = useTranslation();
  const message = t('settings_unsaved_changes_message', {
    defaultValue: '您还有未保存的改动，确定要现在离开吗？',
  });
  const title = t('settings_unsaved_changes_title', {
    defaultValue: '您还有未保存的改动，确定要现在离开吗？',
  });

  return (
    <Modal
      opened={opened}
      onClose={onReturn}
      title={title}
      centered
      closeOnClickOutside={false}
      closeOnEscape={false}
    >
      <Stack>
        <Text>{message}</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onReturn}>
            {t('settings_unsaved_changes_stay', { defaultValue: '返回并检查' })}
          </Button>
          <Button color="red" onClick={onDiscard}>
            {t('settings_unsaved_changes_discard', { defaultValue: '放弃改动并离开' })}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
