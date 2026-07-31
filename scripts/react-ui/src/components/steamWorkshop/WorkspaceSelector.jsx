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
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="发布工作区读取失败">
          {error}
        </Alert>
      )}
      <Paper withBorder p="md" data-remis-surface="paper">
        <Group align="flex-end">
          <Select
            flex={1}
            label="发布工作区"
            placeholder="选择或创建一个工作区"
            data={options}
            value={workspace?.workspace_id || null}
            onChange={onSelect}
          />
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateOpen(true)}
          >
            新建工作区
          </Button>
          <Button
            variant="subtle"
            leftSection={<IconPencil size={16} />}
            disabled={!workspace}
            onClick={openEdit}
          >
            编辑绑定
          </Button>
        </Group>
        {workspace && (
          <Group gap="xs" mt="sm">
            <Badge variant="outline">
              {workspace.project_id ? '已绑定项目' : '未绑定项目'}
            </Badge>
            <Badge variant="outline">
              {workspace.workshop_item_id
                ? `Workshop ID: ${workspace.workshop_item_id}`
                : '尚未绑定 Workshop ID'}
            </Badge>
          </Group>
        )}
      </Paper>
      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建 Steam 发布工作区"
      >
        <div data-remis-surface="elevated">
          <WorkspaceCreateForm
            defaultName={projectName ? `${projectName} 发布素材` : ''}
            isSaving={isSaving}
            onCancel={() => setCreateOpen(false)}
            onCreate={handleCreate}
          />
        </div>
      </Modal>
      <Modal
        opened={editOpen}
        onClose={() => setEditOpen(false)}
        title="编辑发布工作区"
      >
        <Stack data-remis-surface="elevated">
          <TextInput
            required
            label="工作区名称"
            value={editName}
            onChange={(event) => setEditName(event.currentTarget.value)}
          />
          <TextInput
            label="游戏 ID（可选）"
            value={editGameId}
            onChange={(event) => setEditGameId(event.currentTarget.value)}
          />
          <TextInput
            label="Steam Workshop ID（可选）"
            description="可以稍后绑定、替换或清空；项目绑定不会因此改变。"
            value={editWorkshopItemId}
            onChange={(event) => setEditWorkshopItemId(event.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditOpen(false)}>取消</Button>
            <Button
              disabled={!editName.trim()}
              loading={isSaving}
              onClick={handleUpdate}
            >
              保存
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
