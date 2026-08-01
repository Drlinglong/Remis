import React, { useState } from 'react';
import {
  Alert,
  Button,
  Center,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconPlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

import WorkspaceCard from './WorkspaceCard';
import WorkspaceEditorModal from './WorkspaceEditorModal';
import { usePublishingWorkspaceCatalog } from './usePublishingWorkspaceCatalog';
import styles from './SteamWorkshopOverview.module.css';

export default function SteamWorkshopOverview({
  projectId = null,
  projectName = '',
  showHeading = true,
}) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [editingWorkspace, setEditingWorkspace] = useState(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const catalog = usePublishingWorkspaceCatalog({ projectId });

  const openCreate = () => {
    setEditingWorkspace(null);
    setEditorOpen(true);
  };

  const openEdit = (workspace) => {
    setEditingWorkspace(workspace);
    setEditorOpen(true);
  };

  const saveWorkspace = (values) => catalog.saveWorkspace(
    values,
    editingWorkspace?.workspace_id || null,
  );

  return (
    <Stack data-remis-surface="surface" gap="lg" className={styles.overview}>
      {showHeading && (
        <Stack gap="xs" className={styles.headerCopy}>
          <Title order={2}>{projectId ? t('steam_workshop.project_assets_title') : t('steam_workshop.title')}</Title>
          <Text c="dimmed">
            {projectId
              ? t('steam_workshop.overview_project_desc', { project: projectName || projectId })
              : t('steam_workshop.overview_desc')}
          </Text>
        </Stack>
      )}

      <div>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          {t('steam_workshop.create_workspace')}
        </Button>
      </div>

      {catalog.error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title={t('steam_workshop.workspace_load_failed')}>
          {catalog.error}
        </Alert>
      )}

      {catalog.isLoading ? (
        <Center h={220}><Loader type="dots" /></Center>
      ) : catalog.workspaces.length ? (
        <SimpleGrid
          cols={{ base: 1, md: projectId ? 2 : 3 }}
          spacing="lg"
          className={styles.grid}
        >
          {catalog.workspaces.map((workspace) => (
            <WorkspaceCard
              key={workspace.workspace_id}
              workspace={workspace}
              projectName={catalog.projectNames.get(workspace.project_id)}
              onEdit={openEdit}
              onOpen={(workspaceId) => navigate(`/steam-workshop/${workspaceId}/cover`)}
            />
          ))}
        </SimpleGrid>
      ) : (
        <Alert color="blue" title={t('steam_workshop.no_workspace')}>
          {projectId
            ? t('steam_workshop.no_workspace_project_desc')
            : t('steam_workshop.no_workspace_desc')}
        </Alert>
      )}

      <WorkspaceEditorModal
        fixedProjectId={projectId}
        initialWorkspace={editingWorkspace}
        isSaving={catalog.isSaving}
        opened={editorOpen}
        onClose={() => setEditorOpen(false)}
        onSave={saveWorkspace}
        projectName={projectName}
        projects={catalog.projects}
        games={catalog.games}
      />
    </Stack>
  );
}
