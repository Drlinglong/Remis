import React, { Suspense, lazy, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  LoadingOverlay,
  Paper,
  Stack,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import {
  IconArrowLeft,
  IconFileDescription,
  IconHistory,
  IconPencil,
  IconPhoto,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router';

import PublishingVersionHistory from './PublishingVersionHistory';
import WorkspaceEditorModal from './WorkspaceEditorModal';
import { usePublishingWorkspaceDetail } from './usePublishingWorkspaceDetail';

const ThumbnailGenerator = lazy(() => import('../tools/ThumbnailGenerator'));
const WorkshopGenerator = lazy(() => import('../tools/WorkshopGenerator'));

const EditorFallback = () => (
  <Center h={240}>
    <Loader type="dots" />
  </Center>
);

const sections = [
  { value: 'cover', label: '封面图', icon: IconPhoto },
  { value: 'description', label: '工坊描述', icon: IconFileDescription },
  { value: 'history', label: '版本历史', icon: IconHistory },
];

export default function SteamWorkshopWorkspace({ activeSection, workspaceId }) {
  const navigate = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const detail = usePublishingWorkspaceDetail(workspaceId);
  const section = sections.some((item) => item.value === activeSection)
    ? activeSection
    : 'cover';
  const workspace = detail.workspace;

  const navigateSection = (nextSection) => {
    navigate(`/steam-workshop/${workspaceId}/${nextSection || 'cover'}`);
  };

  if (!detail.isLoading && !workspace) {
    return (
      <Alert color="red" title="找不到发布工作区">
        <Button mt="sm" variant="default" onClick={() => navigate('/steam-workshop')}>
          返回工作区总览
        </Button>
      </Alert>
    );
  }

  return (
    <Stack data-remis-surface="surface" gap="lg" pos="relative">
      <LoadingOverlay visible={detail.isLoading} />
      {detail.error && <Alert color="red">{detail.error}</Alert>}

      {workspace && (
        <>
          <Paper withBorder p="lg" data-remis-surface="surface">
            <Stack gap="md">
              <Group justify="space-between" align="flex-start">
                <Group align="flex-start">
                  <Button
                    aria-label="返回工作区总览"
                    variant="subtle"
                    onClick={() => navigate('/steam-workshop')}
                  >
                    <IconArrowLeft size={18} />
                  </Button>
                  <div>
                    <Title order={2}>{workspace.name}</Title>
                    <Text c="dimmed">选择一项发布素材工作，并在独立的版本历史中检视和采用成果。</Text>
                  </div>
                </Group>
                <Button
                  variant="default"
                  leftSection={<IconPencil size={16} />}
                  onClick={() => setEditOpen(true)}
                >
                  编辑绑定
                </Button>
              </Group>
              <Group gap="xs">
                <Badge variant="light">
                  {workspace.project_id
                    ? `项目：${detail.projectName || workspace.project_id}`
                    : '独立工作区'}
                </Badge>
                <Badge variant="outline">
                  {workspace.workshop_item_id
                    ? `Workshop ID: ${workspace.workshop_item_id}`
                    : '尚未绑定 Workshop ID'}
                </Badge>
              </Group>
            </Stack>
          </Paper>

          <Tabs
            value={section}
            onChange={navigateSection}
            keepMounted={false}
            variant="pills"
            radius="md"
          >
            <Tabs.List mb="lg">
              {sections.map((item) => {
                const SectionIcon = item.icon;
                return (
                  <Tabs.Tab
                    key={item.value}
                    value={item.value}
                    leftSection={<SectionIcon size={16} />}
                  >
                    {item.label}
                  </Tabs.Tab>
                );
              })}
            </Tabs.List>

            <Tabs.Panel value="cover">
              <Suspense fallback={<EditorFallback />}>
                {section === 'cover' && (
                  <ThumbnailGenerator
                    projectId={workspace.project_id}
                    workspaceId={workspace.workspace_id}
                    currentCoverVersionId={workspace.current_cover_version_id}
                  />
                )}
              </Suspense>
            </Tabs.Panel>

            <Tabs.Panel value="description">
              <Suspense fallback={<EditorFallback />}>
                {section === 'description' && (
                  <WorkshopGenerator
                    projectId={workspace.project_id}
                    projectName={detail.projectName}
                    workspaceId={workspace.workspace_id}
                    manageWorkspace={false}
                  />
                )}
              </Suspense>
            </Tabs.Panel>

            <Tabs.Panel value="history">
              {section === 'history' && (
                <PublishingVersionHistory workspaceId={workspace.workspace_id} />
              )}
            </Tabs.Panel>
          </Tabs>

          <WorkspaceEditorModal
            initialWorkspace={workspace}
            isSaving={detail.isSaving}
            opened={editOpen}
            onClose={() => setEditOpen(false)}
            onSave={detail.updateWorkspace}
            projects={detail.projects}
          />
        </>
      )}
    </Stack>
  );
}
