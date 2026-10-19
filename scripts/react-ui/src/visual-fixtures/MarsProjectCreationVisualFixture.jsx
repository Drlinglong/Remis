import React, { useState } from 'react';
import { Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { CreateProjectModal } from '../components/projectManagement/CreateProjectModal';

export default function MarsProjectCreationVisualFixture() {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [game, setGame] = useState('surviving_mars');
  const [language, setLanguage] = useState('en');
  const [importMode, setImportMode] = useState('copy');
  const [created, setCreated] = useState('');
  return <>
    {created && <Text data-testid="created-project">{created}</Text>}
    <CreateProjectModal opened={!created} availableGames={[
      { value: 'surviving_mars', label: 'Surviving Mars / Relaunched', supported_language_codes: ['en', 'zh-CN'] },
      { value: 'eu4', label: 'Europa Universalis IV' },
    ]} availableLanguages={[{ value: 'en', label: 'English' }, { value: 'zh-CN', label: '简体中文' }]}
      createProgressMessage="" isCreatingProject={false} newProjectName={name}
      newProjectPath={path} newProjectGame={game} newProjectSourceLang={language}
      newProjectImportMode={importMode} setNewProjectName={setName} setNewProjectPath={setPath}
      setNewProjectGame={setGame} setNewProjectSourceLang={setLanguage} setNewProjectImportMode={setImportMode}
      handleBrowseFolder={() => setPath('J:/SteamLibrary/steamapps/workshop/content/3215050/3816401225')}
      handleCreateProject={() => setCreated('editable-project')} onPipelineCreated={setCreated}
      t={t} onClose={() => {}} />
  </>;
}
