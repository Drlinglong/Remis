import React, { useEffect, useState } from 'react';
import { Button, Group, Modal, Select, Stack, TextInput } from '@mantine/core';

const emptyValues = {
  name: '',
  gameId: '',
  projectId: '',
  workshopItemId: '',
};

export default function WorkspaceEditorModal({
  fixedProjectId = null,
  initialWorkspace = null,
  isSaving,
  opened,
  onClose,
  onSave,
  projectName = '',
  projects = [],
}) {
  const [values, setValues] = useState(emptyValues);

  useEffect(() => {
    if (!opened) return;
    setValues({
      name: initialWorkspace?.name || (projectName ? `${projectName} 发布素材` : ''),
      gameId: initialWorkspace?.game_id || '',
      projectId: fixedProjectId || initialWorkspace?.project_id || '',
      workshopItemId: initialWorkspace?.workshop_item_id || '',
    });
  }, [fixedProjectId, initialWorkspace, opened, projectName]);

  const update = (field, value) => {
    setValues((current) => ({ ...current, [field]: value || '' }));
  };

  const handleSave = async () => {
    if (!values.name.trim()) return;
    const saved = await onSave({
      ...values,
      name: values.name.trim(),
      gameId: values.gameId.trim(),
      workshopItemId: values.workshopItemId.trim(),
    });
    if (saved) onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={initialWorkspace ? '编辑发布工作区' : '新建 Steam 发布工作区'}
    >
      <Stack data-remis-surface="elevated">
        <TextInput
          required
          label="工作区名称"
          value={values.name}
          onChange={(event) => update('name', event.currentTarget.value)}
        />
        <Select
          clearable={!fixedProjectId}
          disabled={Boolean(fixedProjectId)}
          label="绑定 Remis 项目（可选）"
          description="工作区可以绑定已有 Mod 项目，也可以作为独立发布素材存在。"
          placeholder="选择一个项目"
          data={projects.map((project) => ({
            value: project.project_id,
            label: project.name,
          }))}
          value={values.projectId || null}
          onChange={(value) => update('projectId', value)}
        />
        <TextInput
          label="游戏 ID（可选）"
          value={values.gameId}
          onChange={(event) => update('gameId', event.currentTarget.value)}
        />
        <TextInput
          label="Steam Workshop ID（可选）"
          description="首次上传前可以留空；它不会成为项目的必填字段。"
          value={values.workshopItemId}
          onChange={(event) => update('workshopItemId', event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>取消</Button>
          <Button
            disabled={!values.name.trim()}
            loading={isSaving}
            onClick={handleSave}
          >
            {initialWorkspace ? '保存' : '创建工作区'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
