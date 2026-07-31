import React, { Suspense, lazy, useState } from 'react';
import { Alert, Center, Loader, LoadingOverlay, Stack, Tabs, Text, Title } from '@mantine/core';
import { IconFileDescription, IconPhoto } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import WorkspaceSelector from './WorkspaceSelector';
import { usePublishingWorkspaceSelection } from './usePublishingWorkspaceSelection';

const ThumbnailGenerator = lazy(() => import('../tools/ThumbnailGenerator'));
const WorkshopGenerator = lazy(() => import('../tools/WorkshopGenerator'));

const EditorFallback = () => (
  <Center h={240}>
    <Loader type="dots" />
  </Center>
);

export default function SteamWorkshopWorkspace({
  projectId = null,
  projectName = '',
  showHeading = true,
  title = null,
  description = null,
}) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('cover');
  const selection = usePublishingWorkspaceSelection({ projectId });
  const workspaceId = selection.workspace?.workspace_id || null;

  return (
    <Stack data-remis-surface="surface" gap="lg" pos="relative">
      <LoadingOverlay visible={selection.isLoading} />
      {showHeading && (
        <Stack gap="xs">
          <Title order={2}>
            {title || t('page_title_steam_workshop', 'Steam 工坊')}
          </Title>
          <Text c="dimmed">
            {description || t(
              'steam_workshop.description',
              '管理可与项目关联的封面图和工坊描述版本。',
            )}
          </Text>
        </Stack>
      )}

      <WorkspaceSelector
        error={selection.error}
        isSaving={selection.isSaving}
        onCreate={selection.createWorkspace}
        onSelect={selection.selectWorkspace}
        onUpdate={selection.updateWorkspace}
        projectName={projectName}
        workspace={selection.workspace}
        workspaces={selection.workspaces}
      />

      {!selection.workspace && (
        <Alert color="blue" title="先创建发布工作区">
          工作区可以绑定当前项目，也可以暂不填写 Workshop ID。
        </Alert>
      )}

      <Tabs
        value={activeTab}
        onChange={(value) => setActiveTab(value || 'cover')}
        keepMounted={false}
        variant="pills"
        radius="md"
      >
        <Tabs.List mb="lg">
          <Tabs.Tab value="cover" leftSection={<IconPhoto size={16} />}>
            {t('steam_workshop.tabs.cover', '封面图')}
          </Tabs.Tab>
          <Tabs.Tab value="description" leftSection={<IconFileDescription size={16} />}>
            {t('steam_workshop.tabs.description', '工坊描述')}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="cover">
          <Suspense fallback={<EditorFallback />}>
            {activeTab === 'cover' && (
              <ThumbnailGenerator
                projectId={projectId}
                workspaceId={workspaceId}
                currentCoverVersionId={selection.workspace?.current_cover_version_id || null}
              />
            )}
          </Suspense>
        </Tabs.Panel>

        <Tabs.Panel value="description">
          <Suspense fallback={<EditorFallback />}>
            {activeTab === 'description' && (
              <WorkshopGenerator
                projectId={projectId}
                projectName={projectName}
                workspaceId={workspaceId}
                manageWorkspace={false}
              />
            )}
          </Suspense>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
