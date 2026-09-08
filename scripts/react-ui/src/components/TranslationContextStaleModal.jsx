import React from 'react';
import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconArchive, IconBook } from '@tabler/icons-react';

export default function TranslationContextStaleModal({
  detail,
  onCancel,
  onDisableArchive,
  onUseOldArchive,
  opened,
  t,
}) {
  const archive = detail?.context_readiness?.archive || {};
  return (
    <Modal
      opened={opened}
      onClose={onCancel}
      closeOnClickOutside={false}
      title={<Group><IconAlertCircle color="orange" /><Text fw={700}>{t('translation_context_stale.title')}</Text></Group>}
      centered
    >
      <Stack>
        <Text>{t('translation_context_stale.description')}</Text>
        <Alert color="orange" variant="light">
          <Text size="sm">{t('translation_context_stale.release', { release: archive.release_id || '—' })}</Text>
          <Text size="sm">{t('translation_context_stale.hash', { hash: archive.current_source_snapshot_hash || '—' })}</Text>
        </Alert>
        <Text size="sm" c="dimmed">{t('translation_context_stale.question')}</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={onCancel}>{t('translation_context_stale.cancel')}</Button>
          <Button variant="light" leftSection={<IconBook size={16} />} onClick={onDisableArchive}>
            {t('translation_context_stale.disable_archive')}
          </Button>
          <Button leftSection={<IconArchive size={16} />} onClick={onUseOldArchive}>
            {t('translation_context_stale.use_old_archive')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
