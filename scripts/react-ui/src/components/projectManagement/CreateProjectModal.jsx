import React from 'react';
import {
  Alert,
  Box,
  Button,
  Group,
  Modal,
  Progress,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconCopy, IconFolder, IconLink } from '@tabler/icons-react';

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

export function CreateProjectModal({
  availableGames,
  availableLanguages,
  createProgressMessage,
  handleBrowseFolder,
  handleCreateProject,
  isCreatingProject,
  newProjectGame,
  newProjectImportMode,
  newProjectName,
  newProjectPath,
  newProjectSourceLang,
  opened,
  setNewProjectGame,
  setNewProjectImportMode,
  setNewProjectName,
  setNewProjectPath,
  setNewProjectSourceLang,
  t,
  onClose,
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('project_management.actions.create_new')}
      size="lg"
      closeOnClickOutside={!isCreatingProject}
      closeOnEscape={!isCreatingProject}
    >
      <Stack>
        <TextInput
          label={t('form_label_project_name')}
          placeholder={t('form_placeholder_project_name')}
          value={newProjectName}
          onChange={(event) => setNewProjectName(event.currentTarget.value)}
        />
        <Group align="flex-end">
          <TextInput
            label={t('form_label_folder_path')}
            placeholder={t('form_placeholder_folder_path')}
            description={t('form_desc_folder_path')}
            value={newProjectPath}
            onChange={(event) => setNewProjectPath(event.currentTarget.value)}
            style={{ flex: 1 }}
            disabled={isCreatingProject}
          />
          <Button onClick={handleBrowseFolder} leftSection={<IconFolder size={16} />} disabled={isCreatingProject}>
            {t('btn_browse')}
          </Button>
        </Group>
        <SegmentedControl
          fullWidth
          value={newProjectImportMode}
          onChange={setNewProjectImportMode}
          disabled={isCreatingProject}
          data={[
            { value: 'copy', label: t('project_management.import_mode_copy') },
            { value: 'reference', label: t('project_management.import_mode_reference') },
          ]}
        />
        <Alert
          color={newProjectImportMode === 'reference' ? 'yellow' : 'blue'}
          variant="light"
          icon={newProjectImportMode === 'reference' ? <IconLink size={16} /> : <IconCopy size={16} />}
        >
          <Text size="sm">
            {newProjectImportMode === 'reference'
              ? t('project_management.import_mode_reference_desc')
              : t('project_management.import_mode_copy_desc')}
          </Text>
        </Alert>
        <Select
          label={t('form_label_game')}
          data={availableGames.length > 0 ? availableGames : fallbackGames}
          value={newProjectGame}
          onChange={(value) => setNewProjectGame(value)}
          disabled={isCreatingProject}
        />
        <Select
          label={t('form_label_source_language')}
          description={t('form_desc_source_language')}
          data={availableLanguages.length > 0 ? availableLanguages : fallbackLanguages}
          value={newProjectSourceLang}
          onChange={(value) => setNewProjectSourceLang(value)}
          disabled={isCreatingProject}
        />
        {isCreatingProject && (
          <Box>
            <Progress value={100} animated striped />
            <Text size="sm" c="dimmed" mt="xs">{createProgressMessage}</Text>
          </Box>
        )}
        {!isCreatingProject && createProgressMessage && (
          <Text size="sm" c="yellow">{createProgressMessage}</Text>
        )}
        <Button
          onClick={handleCreateProject}
          fullWidth
          mt="md"
          loading={isCreatingProject}
          disabled={!newProjectName || !newProjectPath}
        >
          {isCreatingProject ? t('project_management.create_progress_title') : t('project_management.actions.create_new')}
        </Button>
      </Stack>
    </Modal>
  );
}
