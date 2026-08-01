import React, { useState } from 'react';
import { Button, Group, Stack, TextInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export const WorkspaceCreateForm = ({ defaultName = '', isSaving, onCancel, onCreate }) => {
  const { t } = useTranslation();
  const [name, setName] = useState(defaultName);
  const [gameId, setGameId] = useState('');
  const [workshopItemId, setWorkshopItemId] = useState('');

  const submit = async () => {
    if (!name.trim()) return;
    const created = await onCreate({
      name: name.trim(),
      gameId: gameId.trim(),
      workshopItemId: workshopItemId.trim(),
    });
    if (created) onCancel();
  };

  return (
    <Stack>
      <TextInput
        required
        label={t('steam_workshop.workspace_name')}
        value={name}
        onChange={(event) => setName(event.currentTarget.value)}
      />
      <TextInput
        label={t('steam_workshop.game_id')}
        value={gameId}
        onChange={(event) => setGameId(event.currentTarget.value)}
      />
      <TextInput
        label={t('steam_workshop.workshop_id')}
        description={t('steam_workshop.workshop_id_desc')}
        value={workshopItemId}
        onChange={(event) => setWorkshopItemId(event.currentTarget.value)}
      />
      <Group justify="flex-end">
        <Button variant="default" onClick={onCancel}>{t('steam_workshop.cancel')}</Button>
        <Button disabled={!name.trim()} loading={isSaving} onClick={submit}>{t('steam_workshop.create_workspace_action')}</Button>
      </Group>
    </Stack>
  );
};
