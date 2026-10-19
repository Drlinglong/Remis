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
import { useMarsProjectCreation } from '../../hooks/useMarsProjectCreation';
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
  const isMars = newProjectGame === 'surviving_mars';
  const mars = useMarsProjectCreation({ opened, game: newProjectGame, path: newProjectPath,
    name: newProjectName, language: newProjectSourceLang,
    onCreated: onPipelineCreated, createEditable: handleCreateProject });
  const busy = isCreatingProject || mars.busy;
  const marsLanguageCodes = availableGames.find((game) => game.value === 'surviving_mars')
    ?.supported_language_codes;
  const sourceLanguageOptions = getSourceLanguageOptions(
    availableLanguages,
    isMars,
    marsLanguageCodes,
    t
  );
  const handleGameChange = (gameId) => {
    setNewProjectGame(gameId);
    setMarsImportOpened(false);
    if (gameId === 'surviving_mars') {
      setNewProjectImportMode('copy');
      setNewProjectSourceLang(resolveSupportedSourceLanguage(
        newProjectSourceLang, marsLanguageCodes || ['en', 'zh-CN']
      ));
    }
  };
  const handlePrimaryAction = () => {
    if (isMars) mars.create();
    else handleCreateProject();
  };
  return (
    <Modal
      opened={opened}
      onClose={busy ? () => {} : onClose}
      title={t('project_management.actions.create_new')}
      size="lg"
      closeOnClickOutside={!busy}
      closeOnEscape={!busy}
      withCloseButton={!busy}
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
          disabled={busy}
          onChange={(event) => setNewProjectName(event.currentTarget.value)}
        />
        <Select
          label={t('form_label_game')}
          data={availableGames.length > 0 ? availableGames : getFallbackGames(t)}
          value={newProjectGame}
          onChange={handleGameChange}
          disabled={busy}
        />
        <Group align="flex-end">
          <TextInput
            classNames={{ input: styles.modalInput }}
            label={t('form_label_folder_path')}
            placeholder={t('form_placeholder_folder_path')}
            description={isMars ? t('mars_pipeline.folder_help', 'Choose the Workshop Mod folder containing ModContent.fpk, or an editable Mod folder. Remis discovers the translation text automatically.') : t('form_desc_folder_path')}
            value={newProjectPath}
            onChange={(event) => setNewProjectPath(event.currentTarget.value)}
            style={{ flex: 1 }}
            disabled={busy}
          />
          <Button onClick={handleBrowseFolder} leftSection={<IconFolder size={16} />} disabled={busy}>
            {t('btn_browse')}
          </Button>
        </Group>
        {!isMars && <SegmentedControl
          classNames={{
            root: styles.importModeRoot,
            label: styles.importModeLabel,
            indicator: styles.importModeIndicator,
          }}
          fullWidth
          value={newProjectImportMode}
          onChange={setNewProjectImportMode}
          disabled={busy}
          data={[
            { value: 'copy', label: t('project_management.import_mode_copy') },
            { value: 'reference', label: t('project_management.import_mode_reference') },
          ]}
        />}
        <Alert
          className={styles.importModeAlert}
          color={!isMars && newProjectImportMode === 'reference' ? 'yellow' : 'blue'}
          variant="light"
          icon={!isMars && newProjectImportMode === 'reference' ? <IconLink size={16} /> : <IconCopy size={16} />}
        >
          <Text size="sm">
            {isMars ? t('mars_pipeline.automatic_help', 'Remis unpacks the Mod and prepares its text in an isolated project. Uncertain text stays unchanged and is listed for review after creation.') : newProjectImportMode === 'reference'
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
          disabled={busy}
        />
        {isMars && mars.error && <Alert color="red" role="alert">{mars.error}</Alert>}
        {isMars && !busy && <Button variant="subtle" onClick={() => setMarsImportOpened(true)}>
          {t('mars_pipeline.manual_source_options', 'Advanced source options')}
        </Button>}
        {busy && (
          <Box>
            <Progress value={100} animated striped />
            <Text size="sm" c="dimmed" mt="xs">{mars.busy
              ? t(`mars_pipeline.creation_${mars.stage}`, 'Preparing the Mod and translation text…') : createProgressMessage}</Text>
          </Box>
        )}
        {!busy && createProgressMessage && (
          <Text size="sm" c="yellow">{createProgressMessage}</Text>
        )}
        <Button
          onClick={handlePrimaryAction}
          fullWidth
          mt="md"
          loading={busy}
          disabled={busy || !newProjectName.trim() || !newProjectPath.trim() || !newProjectSourceLang}
        >
          {busy ? t('project_management.create_progress_title') : t('project_management.actions.create_new')}
        </Button>
      </Stack>
      <MarsPipelineImport opened={marsImportOpened} onClose={() => setMarsImportOpened(false)}
        sourceLanguage={resolveSupportedSourceLanguage(newProjectSourceLang, marsLanguageCodes || [])}
        languageOptions={sourceLanguageOptions.length > 0 ? sourceLanguageOptions : fallbackLanguages}
        onUseExistingCsv={() => {
          setNewProjectSourceLang(resolveSupportedSourceLanguage(
            newProjectSourceLang,
            marsLanguageCodes || []
          ));
          setMarsImportOpened(false);
        }}
        name={newProjectName} onCreated={(projectId) => {
          setMarsImportOpened(false);
          onPipelineCreated?.(projectId);
        }} />
    </Modal>
  );
}
