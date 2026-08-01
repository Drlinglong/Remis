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
import { useNavigate, useSearchParams } from 'react-router';
import { useTranslation } from 'react-i18next';

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

export default function SteamWorkshopWorkspace({ activeSection, workspaceId }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const sections = [
    { value: 'cover', label: t('steam_workshop.cover_label'), icon: IconPhoto },
    { value: 'description', label: t('steam_workshop.description'), icon: IconFileDescription },
    { value: 'history', label: t('steam_workshop.history'), icon: IconHistory },
  ];
  const [searchParams] = useSearchParams();
  const [editOpen, setEditOpen] = useState(false);
  const detail = usePublishingWorkspaceDetail(workspaceId);
  const section = sections.some((item) => item.value === activeSection)
    ? activeSection
    : 'cover';
  const coverVersionId = section === 'cover' ? searchParams.get('coverVersionId') : null;
  const workspace = detail.workspace;

  const navigateSection = (nextSection) => {
    navigate(`/steam-workshop/${workspaceId}/${nextSection || 'cover'}`);
  };

  if (!detail.isLoading && !workspace) {
    return (
      <Alert color="red" title={t('steam_workshop.workspace_not_found')}>
        <Button mt="sm" variant="default" onClick={() => navigate('/steam-workshop')}>
          {t('steam_workshop.back_to_overview')}
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
          <Paper withBorder p="lg" data-remis-surface="paper">
            <Stack gap="md">
              <Group justify="space-between" align="flex-start">
                <Group align="flex-start">
                  <Button
                    aria-label={t('steam_workshop.back_to_overview')}
                    variant="subtle"
                    onClick={() => navigate('/steam-workshop')}
                  >
                    <IconArrowLeft size={18} />
                  </Button>
                  <div>
                    <Title order={2}>{workspace.name}</Title>
                    <Text c="dimmed">{t('steam_workshop.workspace_desc')}</Text>
                  </div>
                </Group>
                <Button
                  variant="default"
                  leftSection={<IconPencil size={16} />}
                  onClick={() => setEditOpen(true)}
                >
                  {t('steam_workshop.edit_binding')}
                </Button>
              </Group>
              <Group gap="xs">
                <Badge variant="light">
                  {workspace.project_id
                    ? t('steam_workshop.project_context', { project: detail.projectName || workspace.project_id })
                    : t('steam_workshop.independent_workspace')}
                </Badge>
                <Badge variant="outline">
                  {workspace.workshop_item_id
                    ? `Workshop ID: ${workspace.workshop_item_id}`
                    : t('steam_workshop.workshop_id_unbound')}
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
                    editCoverVersionId={coverVersionId}
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
