import React from 'react';
import {
  Alert, Badge, Button, Checkbox, Code, Group, Modal, ScrollArea, Stack, Text,
} from '@mantine/core';

const STATUS_COLORS = { ready: 'green', stale: 'orange', missing: 'gray' };

export default function ReferenceLibraryDiscoveryModal({
  t,
  opened,
  candidates,
  selectedIds,
  loading,
  onToggle,
  onConfirm,
  onClose,
}) {
  const selectedCount = candidates.filter((candidate) => selectedIds.has(candidate.game_id)).length;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('settings_reference_discovery_title')}
      centered
      size="xl"
    >
      <Stack gap="md">
        <Alert color="blue" title={t('settings_reference_discovery_notice_title')}>
          {t('settings_reference_discovery_notice')}
        </Alert>
        {candidates.length === 0 ? (
          <Text c="dimmed">{t('settings_reference_none_found')}</Text>
        ) : (
          <ScrollArea.Autosize mah={360} type="auto">
            <Stack gap="xs">
              {candidates.map((candidate) => {
                const status = candidate.status || 'missing';
                return (
                  <Checkbox
                    key={`${candidate.game_id}:${candidate.localization_path}`}
                    checked={selectedIds.has(candidate.game_id)}
                    onChange={() => onToggle(candidate.game_id)}
                    label={(
                      <Stack gap={2} ml="xs">
                        <Group gap="xs">
                          <Text fw={600} size="sm">{candidate.game_name || candidate.game_id}</Text>
                          <Badge size="sm" color={STATUS_COLORS[status] || 'gray'}>
                            {t(`settings_reference_${status}`)}
                          </Badge>
                        </Group>
                        <Code fz="xs" style={{ whiteSpace: 'normal', wordBreak: 'break-all' }}>
                          {candidate.localization_path || candidate.root_path}
                        </Code>
                        {candidate.game_version && (
                          <Text size="xs" c="dimmed">
                            {t('settings_reference_version')}: {candidate.game_version}
                          </Text>
                        )}
                      </Stack>
                    )}
                  />
                );
              })}
            </Stack>
          </ScrollArea.Autosize>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{t('common.cancel')}</Button>
          <Button loading={loading} disabled={selectedCount === 0} onClick={onConfirm}>
            {t('settings_reference_start_selected', { count: selectedCount })}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
