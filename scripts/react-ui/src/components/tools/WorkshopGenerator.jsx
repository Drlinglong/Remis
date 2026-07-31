import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  CopyButton,
  Grid,
  Group,
  LoadingOverlay,
  Modal,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconCheck, IconCopy, IconDeviceFloppy } from '@tabler/icons-react';
import { BbcodePreview } from '../steamWorkshop/description/BbcodePreview';
import { DescriptionGenerationPanel } from '../steamWorkshop/description/DescriptionGenerationPanel';
import { useDescriptionWorkspace } from '../steamWorkshop/description/useDescriptionWorkspace';
import { WorkspaceCreateForm } from '../steamWorkshop/description/WorkspaceCreateForm';

const DEFAULT_TEMPLATE = `[h1]模组标题[/h1]

[b]在这里编写 Steam 工坊描述。[/b]

[h2]特色[/h2]
[list]
[*]特色一
[*]特色二
[/list]`;

const editorStateForVersion = (version) => ({
  bbcode: version?.bbcode || '',
  language: version?.language || 'zh',
  parentVersionId: version?.version_id || null,
});

const WorkshopGenerator = ({
  projectId = null,
  projectName = '',
  workspaceId = null,
  manageWorkspace = true,
}) => {
  const [createOpen, setCreateOpen] = useState(false);
  const {
    createWorkspace,
    editor,
    error,
    generateCandidate,
    isGenerating,
    isLoading,
    isSaving,
    saveCandidate,
    selectWorkspace,
    setEditor,
    versions,
    workspace,
    workspaces,
  } = useDescriptionWorkspace({
    projectId,
    requestedWorkspaceId: workspaceId,
  });

  const adoptedVersion = versions.find(
    (version) => version.version_id === workspace?.current_description_version_id,
  ) || null;
  const latestVersion = versions[0] || null;
  const preferredVersion = adoptedVersion || latestVersion;
  const workspaceEntryKey = workspace
    ? `${workspace.workspace_id}:${workspace.current_description_version_id || 'none'}`
    : null;
  const initializedEntryRef = useRef(null);

  useEffect(() => {
    if (!workspaceEntryKey) {
      initializedEntryRef.current = null;
      return;
    }
    if (isLoading || initializedEntryRef.current === workspaceEntryKey) return;

    setEditor(editorStateForVersion(preferredVersion));
    initializedEntryRef.current = workspaceEntryKey;
  }, [isLoading, preferredVersion, setEditor, workspaceEntryKey]);

  const updateEditor = (field, value) => {
    setEditor((current) => ({ ...current, [field]: value }));
  };

  const handleSave = async () => {
    const saved = await saveCandidate();
    if (!saved) return;
    notifications.show({
      title: '候选版本已保存',
      message: `版本 ${saved.sequence} 已持久化，但尚未设为当前采用。`,
      color: 'green',
    });
  };

  const handleGenerate = async (payload) => {
    const generated = await generateCandidate(payload);
    if (!generated) return null;

    notifications.show({
      title: '模型候选版本已保存',
      message: `版本 ${generated.sequence} 已生成，尚未设为当前采用。`,
      color: 'green',
    });

    if (adoptedVersion) {
      setEditor(editorStateForVersion(adoptedVersion));
    }
    return generated;
  };

  const workspaceOptions = workspaces.map((item) => ({
    value: item.workspace_id,
    label: item.name,
  }));

  return (
    <div
      data-remis-surface="surface"
      style={{
        maxWidth: 1400,
        margin: '0 auto',
        padding: 24,
        position: 'relative',
        minWidth: 0,
      }}
    >
      <LoadingOverlay visible={isLoading} />
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={2}>工坊描述</Title>
            <Text c="dimmed">
              编辑安全可预览的 BBCode，并把成果保存为可回溯的候选版本。
            </Text>
          </div>
          {projectId && <Badge variant="light">已绑定项目：{projectName || projectId}</Badge>}
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" title="操作失败">
            {typeof error === 'string' ? error : '请求失败，请稍后重试。'}
          </Alert>
        )}

        {manageWorkspace && <Paper withBorder p="md" data-remis-surface="paper">
          <Group align="flex-end">
            <Select
              flex={1}
              label="发布工作区"
              placeholder="选择工作区"
              data={workspaceOptions}
              value={workspace?.workspace_id || null}
              onChange={selectWorkspace}
              disabled={Boolean(workspaceId)}
            />
            <Button variant="default" onClick={() => setCreateOpen(true)}>
              新建工作区
            </Button>
          </Group>
          {workspace && (
            <Group gap="xs" mt="sm">
              <Badge variant="outline">
                {workspace.workshop_item_id
                  ? `Workshop ID: ${workspace.workshop_item_id}`
                  : '尚未绑定 Workshop ID'}
              </Badge>
              <Badge variant="outline">
                {workspace.project_id ? '项目工作区' : '未绑定项目'}
              </Badge>
            </Group>
          )}
        </Paper>}

        {!workspace && (
          <Alert color="blue" title="先创建发布工作区">
            工作区可以绑定当前项目，也可以不填写 Workshop ID。素材版本不会依赖远端物品存在。
          </Alert>
        )}

        {workspace && (
          <>
            <DescriptionGenerationPanel
              isGenerating={isGenerating}
              onGenerate={handleGenerate}
              workshopItemId={workspace.workshop_item_id}
            />

            <Grid gutter="lg">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack>
                    <TextInput
                      label="手工候选语言"
                      description="手工保存时记录的版本语言；模型生成请使用上方的“描述语言”。"
                      value={editor.language}
                      onChange={(event) => updateEditor('language', event.currentTarget.value)}
                    />
                    <Textarea
                      label="Steam BBCode"
                      minRows={20}
                      autosize
                      maxRows={32}
                      value={editor.bbcode}
                      placeholder={DEFAULT_TEMPLATE}
                      onChange={(event) => updateEditor('bbcode', event.currentTarget.value)}
                      styles={{ input: { fontFamily: 'monospace' } }}
                    />
                    <Group justify="space-between">
                      <CopyButton value={editor.bbcode}>
                        {({ copied, copy }) => (
                          <Tooltip label={copied ? '已复制' : '复制 BBCode'}>
                            <Button
                              variant="default"
                              leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                              onClick={copy}
                            >
                              {copied ? '已复制' : '复制'}
                            </Button>
                          </Tooltip>
                        )}
                      </CopyButton>
                      <Button
                        leftSection={<IconDeviceFloppy size={16} />}
                        disabled={!editor.bbcode.trim()}
                        loading={isSaving}
                        onClick={handleSave}
                      >
                        保存候选版本
                      </Button>
                    </Group>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Title order={4} mb="sm">安全预览</Title>
                  <BbcodePreview bbcode={editor.bbcode} />
                </Grid.Col>
            </Grid>
            <Text c="dimmed" size="xs">
              已保存版本请前往独立的“版本历史”页面检视和采用。
            </Text>
          </>
        )}
      </Stack>

      {manageWorkspace && <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建 Steam 发布工作区"
      >
        <div data-remis-surface="elevated">
          <WorkspaceCreateForm
            defaultName={projectName ? `${projectName} 发布素材` : ''}
            isSaving={isSaving}
            onCancel={() => setCreateOpen(false)}
            onCreate={createWorkspace}
          />
        </div>
      </Modal>}
    </div>
  );
};

export default WorkshopGenerator;
