import React from 'react';
import { Button, Group, Modal, Stack, Text } from '@mantine/core';

export default function ReferenceLibraryDeleteModal({
  t, opened, game, loading, onClose, onConfirm,
}) {
  if (!game) return null;
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('settings_reference_delete_title')}
      centered
    >
      <Stack gap="md">
        <Text>
          {t('settings_reference_delete_description', { game: game.game_name || game.game_id })}
        </Text>
        <Text size="sm" c="dimmed">{t('settings_reference_delete_warning')}</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{t('cancel')}</Button>
          <Button color="red" loading={loading} onClick={onConfirm}>
            {t('settings_reference_delete_confirm')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
