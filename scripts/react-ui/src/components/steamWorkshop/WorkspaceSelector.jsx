import React, { useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Group,
  Modal,
  Paper,
  Select,
  Stack,
  TextInput,
} from '@mantine/core';
import { IconAlertCircle, IconPencil, IconPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { WorkspaceCreateForm } from './description/WorkspaceCreateForm';

export default function WorkspaceSelector({
  error,
  isSaving,
  onCreate,
  onSelect,
  onUpdate,
  projectName = '',
  workspace,
  workspaces,
}) {
  const { t } = useTranslation();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editGameId, setEditGameId] = useState('');
  const [editWorkshopItemId, setEditWorkshopItemId] = useState('');
  const options = workspaces.map((item) => ({
    value: item.workspace_id,
    label: item.name,
  }));

  const handleCreate = async (values) => {
    const created = await onCreate(values);
    if (created) setCreateOpen(false);
  };

  const openEdit = () => {
    setEditName(workspace?.name || '');
    setEditGameId(workspace?.game_id || '');
    setEditWorkshopItemId(workspace?.workshop_item_id || '');
    setEditOpen(true);
  };

  const handleUpdate = async () => {
    const updated = await onUpdate({
      name: editName.trim(),
      gameId: editGameId.trim(),
      workshopItemId: editWorkshopItemId.trim(),
    });
    if (updated) setEditOpen(false);
  };

  return (
    <>
      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title={t('steam_workshop.workspace_load_failed')}>
          {error}
        </Alert>
      )}
      <Paper withBorder p="md" data-remis-surface="paper">
        <Group align="flex-end">
          <Select
            flex={1}
            label={t('steam_workshop.workspace')}
            placeholder={t('steam_workshop.select_or_create_workspace')}
            data={options}
            value={workspace?.workspace_id || null}
            onChange={onSelect}
          />
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateOpen(true)}
          >
            {t('steam_workshop.create_workspace')}
          </Button>
          <Button
            variant="subtle"
            leftSection={<IconPencil size={16} />}
            disabled={!workspace}
            onClick={openEdit}
          >
            {t('steam_workshop.edit_binding')}
          </Button>
        </Group>
        {workspace && (
          <Group gap="xs" mt="sm">
            <Badge variant="outline">
              {workspace.project_id ? t('steam_workshop.project_bound') : t('steam_workshop.project_unbound')}
            </Badge>
            <Badge variant="outline">
              {workspace.workshop_item_id
                ? `Workshop ID: ${workspace.workshop_item_id}`
                : t('steam_workshop.workshop_id_unbound')}
            </Badge>
          </Group>
        )}
      </Paper>
      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title={t('steam_workshop.new_workspace')}
      >
        <div data-remis-surface="elevated">
          <WorkspaceCreateForm
            defaultName={projectName ? t('steam_workshop.project_assets_name', { project: projectName }) : ''}
            isSaving={isSaving}
            onCancel={() => setCreateOpen(false)}
            onCreate={handleCreate}
          />
        </div>
      </Modal>
      <Modal
        opened={editOpen}
        onClose={() => setEditOpen(false)}
        title={t('steam_workshop.edit_workspace')}
      >
        <Stack data-remis-surface="elevated">
          <TextInput
            required
            label={t('steam_workshop.workspace_name')}
            value={editName}
            onChange={(event) => setEditName(event.currentTarget.value)}
          />
          <TextInput
            label={t('steam_workshop.game_id')}
            value={editGameId}
            onChange={(event) => setEditGameId(event.currentTarget.value)}
          />
          <TextInput
            label={t('steam_workshop.workshop_id')}
            description={t('steam_workshop.workshop_id_replace_desc')}
            value={editWorkshopItemId}
            onChange={(event) => setEditWorkshopItemId(event.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditOpen(false)}>{t('steam_workshop.cancel')}</Button>
            <Button
              disabled={!editName.trim()}
              loading={isSaving}
              onClick={handleUpdate}
            >
              {t('steam_workshop.save')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
