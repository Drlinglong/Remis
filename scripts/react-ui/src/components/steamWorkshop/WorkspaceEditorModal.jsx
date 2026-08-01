import React, { useEffect, useState } from 'react';
import { Button, Group, Modal, Select, Stack, TextInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';

const emptyValues = {
  name: '',
  gameId: '',
  projectId: '',
  workshopItemId: '',
};

export default function WorkspaceEditorModal({
  fixedProjectId = null,
  games = [],
  initialWorkspace = null,
  isSaving,
  opened,
  onClose,
  onSave,
  projectName = '',
  projects = [],
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState(emptyValues);

  useEffect(() => {
    if (!opened) return;
    setValues({
      name: initialWorkspace?.name || (projectName ? t('steam_workshop.project_assets_name', { project: projectName }) : ''),
      gameId: initialWorkspace?.game_id || '',
      projectId: fixedProjectId || initialWorkspace?.project_id || '',
      workshopItemId: initialWorkspace?.workshop_item_id || '',
    });
  // The name is initialized when this modal opens; it must not reset while a user edits it.
  // `t` is stable in the application, but test doubles may not preserve that identity.
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      data-remis-surface="elevated"
      title={initialWorkspace ? t('steam_workshop.edit_workspace') : t('steam_workshop.new_workspace')}
    >
      <Stack data-remis-surface="elevated">
        <TextInput
          required
          label={t('steam_workshop.workspace_name')}
          value={values.name}
          onChange={(event) => update('name', event.currentTarget.value)}
        />
        <Select
          clearable={!fixedProjectId}
          disabled={Boolean(fixedProjectId)}
          label={t('steam_workshop.bind_project')}
          description={t('steam_workshop.bind_project_desc')}
          placeholder={t('steam_workshop.select_project')}
          data={projects.map((project) => ({
            value: project.project_id,
            label: project.name,
          }))}
          value={values.projectId || null}
          onChange={(value) => update('projectId', value)}
        />
        <Select
          clearable
          searchable
          label={t('steam_workshop.game')}
          description={t('steam_workshop.game_desc')}
          placeholder={t('steam_workshop.select_game')}
          data={games}
          value={values.gameId || null}
          onChange={(value) => update('gameId', value)}
        />
        <TextInput
          label={t('steam_workshop.workshop_id')}
          description={t('steam_workshop.workshop_id_desc')}
          value={values.workshopItemId}
          onChange={(event) => update('workshopItemId', event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{t('steam_workshop.cancel')}</Button>
          <Button
            disabled={!values.name.trim()}
            loading={isSaving}
            onClick={handleSave}
          >
            {initialWorkspace ? t('steam_workshop.save') : t('steam_workshop.create_workspace_action')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
