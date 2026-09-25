import React, { useState } from 'react';
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
import styles from './CreateProjectModal.module.css';
import MarsPipelineImport from '../project/MarsPipelineImport';
import {
  getSourceLanguageOptions,
  resolveSupportedSourceLanguage,
} from '../../utils/projectLanguages';

const getFallbackGames = (t) => [
  { value: 'stellaris', label: 'Stellaris' },
  { value: 'hoi4', label: 'Hearts of Iron IV' },
  { value: 'vic3', label: 'Victoria 3' },
  { value: 'ck3', label: 'Crusader Kings III' },
  { value: 'eu4', label: 'Europa Universalis IV' },
  { value: 'project_zomboid', label: t('game_name_project_zomboid', 'Project Zomboid') },
  { value: 'rimworld', label: t('game_name_rimworld', 'RimWorld') },
  { value: 'surviving_mars', label: 'Surviving Mars / Relaunched' },
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
  onPipelineCreated,
}) {
  const [marsImportOpened, setMarsImportOpened] = useState(false);
  const [marsCsvMode, setMarsCsvMode] = useState(false);
  const isMars = newProjectGame === 'surviving_mars';
  const marsLanguageCodes = availableGames.find((game) => game.value === 'surviving_mars')
    ?.supported_language_codes;
  const sourceLanguageOptions = getSourceLanguageOptions(
    availableLanguages,
    isMars,
    marsLanguageCodes,
    t
  );
  const useFpkFlow = isMars && !marsCsvMode;
  const handleGameChange = (gameId) => {
    setNewProjectGame(gameId);
    setMarsCsvMode(false);
    if (gameId === 'surviving_mars') setMarsImportOpened(true);
    else setMarsImportOpened(false);
  };
  const handlePrimaryAction = () => {
    if (useFpkFlow) setMarsImportOpened(true);
    else handleCreateProject();
  };
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('project_management.actions.create_new')}
      size="lg"
      closeOnClickOutside={!isCreatingProject}
      closeOnEscape={!isCreatingProject}
      classNames={{
        content: styles.modalContent,
        header: styles.modalHeader,
        title: styles.modalTitle,
        body: styles.modalBody,
        close: styles.modalClose,
      }}
    >
      <Stack data-remis-surface="paper">
        <TextInput
          classNames={{ input: styles.modalInput }}
          label={t('form_label_project_name')}
          placeholder={t('form_placeholder_project_name')}
          value={newProjectName}
          onChange={(event) => setNewProjectName(event.currentTarget.value)}
        />
        <Select
          label={t('form_label_game')}
          data={availableGames.length > 0 ? availableGames : getFallbackGames(t)}
          value={newProjectGame}
          onChange={handleGameChange}
          disabled={isCreatingProject}
        />
        {useFpkFlow && (
          <Alert className={styles.importModeAlert} color="blue" variant="light">
            <Text size="sm">{t('mars_pipeline.game_selected_help', 'Next, choose a compiled Mod archive to prepare an isolated translation project.')}</Text>
            <Button variant="light" mt="sm" onClick={() => setMarsImportOpened(true)}>
              {t('mars_pipeline.reopen_import', 'Reopen FPK preparation')}
            </Button>
          </Alert>
        )}
        {(!isMars || marsCsvMode) && <>
        <Group align="flex-end">
          <TextInput
            classNames={{ input: styles.modalInput }}
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
          classNames={{
            root: styles.importModeRoot,
            label: styles.importModeLabel,
            indicator: styles.importModeIndicator,
          }}
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
          className={styles.importModeAlert}
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
          label={t('form_label_source_language')}
          description={t('form_desc_source_language')}
          data={sourceLanguageOptions.length > 0 ? sourceLanguageOptions : fallbackLanguages}
          value={newProjectSourceLang}
          onChange={(value) => setNewProjectSourceLang(value)}
          disabled={isCreatingProject}
        />
        {isMars && <Button variant="subtle" onClick={() => {
          setMarsCsvMode(false);
          setMarsImportOpened(true);
        }}>{t('mars_pipeline.open_import', 'Open FPK preparation')}</Button>}
        </>}
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
          onClick={handlePrimaryAction}
          fullWidth
          mt="md"
          loading={isCreatingProject}
          disabled={isCreatingProject || (!useFpkFlow && (!newProjectName || !newProjectPath))}
        >
          {isCreatingProject ? t('project_management.create_progress_title')
            : useFpkFlow ? t('mars_pipeline.open_import', 'Open FPK preparation') : t('project_management.actions.create_new')}
        </Button>
      </Stack>
      <MarsPipelineImport opened={marsImportOpened} onClose={() => setMarsImportOpened(false)}
        onUseExistingCsv={() => {
          setNewProjectSourceLang(resolveSupportedSourceLanguage(
            newProjectSourceLang,
            marsLanguageCodes || []
          ));
          setMarsCsvMode(true);
          setMarsImportOpened(false);
        }}
        name={newProjectName} onCreated={(projectId) => {
          setMarsImportOpened(false);
          onPipelineCreated?.(projectId);
        }} />
    </Modal>
  );
}
