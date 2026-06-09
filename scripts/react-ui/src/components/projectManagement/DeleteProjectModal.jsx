import React from 'react';
import { Alert, Button, Checkbox, Group, Modal, Paper, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconTrash } from '@tabler/icons-react';

export function DeleteProjectModal({
  deleteSourceFiles,
  handleDeleteForever,
  opened,
  selectedProject,
  setDeleteSourceFiles,
  t,
  onClose,
}) {
  const handleClose = () => {
    onClose();
    setDeleteSourceFiles(false);
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={(
        <Group>
          <IconAlertTriangle color="red" size={24} />
          <Text fw={700} c="red">{t('project_management.delete_forever')}</Text>
        </Group>
      )}
      size="md"
      centered
    >
      <Stack>
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={16} />}>
          <Text size="sm" fw={600}>{t('project_management.delete_modal_warning')}</Text>
          <Text size="xs" c="dimmed" mt={4}>{t('project_management.delete_modal_warning_desc')}</Text>
        </Alert>

        <Text size="sm">
          {t('project_management.delete_modal_question')}
        </Text>
        <Paper withBorder p="xs" bg="rgba(255, 0, 0, 0.05)">
          <Text size="sm" fw={600}>{selectedProject?.name}</Text>
          <Text size="xs" c="dimmed">{selectedProject?.source_path}</Text>
        </Paper>

        <Checkbox
          checked={deleteSourceFiles}
          onChange={(event) => setDeleteSourceFiles(event.currentTarget.checked)}
          label={(
            <div>
              <Text size="sm" fw={600} c="red">{t('project_management.delete_modal_source_files_label')}</Text>
              <Text size="xs" c="dimmed">{t('project_management.delete_modal_source_files_desc')}</Text>
            </div>
          )}
          color="red"
          size="md"
          mt="md"
        />

        <Group justify="flex-end" mt="xl">
          <Button variant="default" onClick={handleClose}>
            {t('button_cancel')}
          </Button>
          <Button color="red" leftSection={<IconTrash size={16} />} onClick={handleDeleteForever}>
            {deleteSourceFiles ? t('project_management.delete_modal_btn_with_files') : t('project_management.delete_modal_btn_config_only')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
