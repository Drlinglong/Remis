import React, { useState } from 'react';
import { Button, Group, Stack, TextInput } from '@mantine/core';

export const WorkspaceCreateForm = ({ defaultName = '', isSaving, onCancel, onCreate }) => {
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
        label="工作区名称"
        value={name}
        onChange={(event) => setName(event.currentTarget.value)}
      />
      <TextInput
        label="游戏 ID（可选）"
        value={gameId}
        onChange={(event) => setGameId(event.currentTarget.value)}
      />
      <TextInput
        label="Steam Workshop ID（可选）"
        description="首次上传前可以留空；它不会成为项目的必填字段。"
        value={workshopItemId}
        onChange={(event) => setWorkshopItemId(event.currentTarget.value)}
      />
      <Group justify="flex-end">
        <Button variant="default" onClick={onCancel}>取消</Button>
        <Button disabled={!name.trim()} loading={isSaving} onClick={submit}>创建工作区</Button>
      </Group>
    </Stack>
  );
};
