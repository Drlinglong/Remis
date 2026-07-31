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
          <Title order={2}>{projectId ? '发布素材管理' : 'Steam 工坊'}</Title>
          <Text c="dimmed">
            {projectId
              ? `集中管理“${projectName || projectId}”的 Steam 发布工作区。`
              : '创建并进入发布工作区，再分别处理封面图、工坊描述和版本历史。'}
          </Text>
        </Stack>
      )}

      <div>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          新建工作区
        </Button>
      </div>

      {catalog.error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="工作区读取失败">
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
        <Alert color="blue" title="还没有发布工作区">
          {projectId
            ? '为当前项目创建工作区后，封面图、工坊描述和版本历史会集中在这里。'
            : '发布工作区可以绑定已有 Remis 项目，也可以先作为独立素材工作区创建。'}
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
      />
    </Stack>
  );
}
