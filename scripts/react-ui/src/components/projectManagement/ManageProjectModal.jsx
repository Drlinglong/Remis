import React from 'react';
import { Button, Group, Modal, Select, Stack } from '@mantine/core';

const fallbackGames = [
  { value: 'stellaris', label: 'Stellaris' },
  { value: 'hoi4', label: 'Hearts of Iron IV' },
  { value: 'vic3', label: 'Victoria 3' },
  { value: 'ck3', label: 'Crusader Kings III' },
  { value: 'eu4', label: 'Europa Universalis IV' },
];

const fallbackLanguages = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: 'Simplified Chinese' },
];

export function ManageProjectModal({
  availableGames,
  availableLanguages,
  editGameId,
  editSourceLang,
  handleUpdateMetadata,
  opened,
  setEditGameId,
  setEditSourceLang,
  t,
  onClose,
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('project_management.manage_project')}
      size="lg"
    >
      <Stack>
        <Select
          label={t('form_label_game')}
          data={availableGames.length > 0 ? availableGames : fallbackGames}
          value={editGameId ? editGameId.toLowerCase() : ''}
          onChange={setEditGameId}
        />
        <Select
          label={t('form_label_source_language')}
          data={availableLanguages.length > 0 ? availableLanguages : fallbackLanguages}
          value={editSourceLang}
          onChange={setEditSourceLang}
        />
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={onClose}>{t('button_cancel')}</Button>
          <Button onClick={handleUpdateMetadata}>{t('settings_save')}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
