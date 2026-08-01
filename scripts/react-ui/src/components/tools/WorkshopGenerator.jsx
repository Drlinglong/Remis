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
import { useTranslation } from 'react-i18next';
import { BbcodePreview } from '../steamWorkshop/description/BbcodePreview';
import { DescriptionGenerationPanel } from '../steamWorkshop/description/DescriptionGenerationPanel';
import { useDescriptionWorkspace } from '../steamWorkshop/description/useDescriptionWorkspace';
import { WorkspaceCreateForm } from '../steamWorkshop/description/WorkspaceCreateForm';

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
  const { t } = useTranslation();
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
      title: t('steam_workshop.candidate_saved'),
      message: t('steam_workshop.candidate_saved_desc', { sequence: saved.sequence }),
      color: 'green',
    });
  };

  const handleGenerate = async (payload) => {
    const generated = await generateCandidate(payload);
    if (!generated) return null;

    notifications.show({
      title: t('steam_workshop.model_candidate_saved'),
      message: t('steam_workshop.model_candidate_saved_desc', { sequence: generated.sequence }),
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
            <Title order={2}>{t('steam_workshop.description')}</Title>
            <Text c="dimmed">
              {t('steam_workshop.description_intro')}
            </Text>
          </div>
          {projectId && <Badge variant="light">{t('steam_workshop.bound_project', { project: projectName || projectId })}</Badge>}
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" title={t('steam_workshop.operation_failed')}>
            {typeof error === 'string' ? error : t('steam_workshop.request_failed')}
          </Alert>
        )}

        {manageWorkspace && <Paper withBorder p="md" data-remis-surface="paper">
          <Group align="flex-end">
            <Select
              flex={1}
              label={t('steam_workshop.workspace')}
              placeholder={t('steam_workshop.select_workspace')}
              data={workspaceOptions}
              value={workspace?.workspace_id || null}
              onChange={selectWorkspace}
              disabled={Boolean(workspaceId)}
            />
            <Button variant="default" onClick={() => setCreateOpen(true)}>
              {t('steam_workshop.create_workspace')}
            </Button>
          </Group>
          {workspace && (
            <Group gap="xs" mt="sm">
              <Badge variant="outline">
                {workspace.workshop_item_id
                  ? `Workshop ID: ${workspace.workshop_item_id}`
                  : t('steam_workshop.workshop_id_unbound')}
              </Badge>
              <Badge variant="outline">
                {workspace.project_id ? t('steam_workshop.project_workspace') : t('steam_workshop.project_unbound')}
              </Badge>
            </Group>
          )}
        </Paper>}

        {!workspace && (
          <Alert color="blue" title={t('steam_workshop.create_workspace_first')}>
            {t('steam_workshop.create_workspace_first_desc')}
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
                      label={t('steam_workshop.manual_candidate_language')}
                      description={t('steam_workshop.manual_candidate_language_desc')}
                      value={editor.language}
                      onChange={(event) => updateEditor('language', event.currentTarget.value)}
                    />
                    <Textarea
                      label={t('steam_workshop.bbcode')}
                      minRows={20}
                      autosize
                      maxRows={32}
                      value={editor.bbcode}
                      placeholder={t('steam_workshop.default_template')}
                      onChange={(event) => updateEditor('bbcode', event.currentTarget.value)}
                      styles={{ input: { fontFamily: 'monospace' } }}
                    />
                    <Group justify="space-between">
                      <CopyButton value={editor.bbcode}>
                        {({ copied, copy }) => (
                          <Tooltip label={copied ? t('steam_workshop.copied') : t('steam_workshop.copy_bbcode')}>
                            <Button
                              variant="default"
                              leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                              onClick={copy}
                            >
                              {copied ? t('steam_workshop.copied') : t('steam_workshop.copy')}
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
                        {t('steam_workshop.save_candidate')}
                      </Button>
                    </Group>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Title order={4} mb="sm">{t('steam_workshop.safe_preview')}</Title>
                  <BbcodePreview bbcode={editor.bbcode} />
                </Grid.Col>
            </Grid>
            <Text c="dimmed" size="xs">
              {t('steam_workshop.saved_versions_notice')}
            </Text>
          </>
        )}
      </Stack>

      {manageWorkspace && <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title={t('steam_workshop.new_workspace')}
      >
        <div data-remis-surface="elevated">
          <WorkspaceCreateForm
            defaultName={projectName ? t('steam_workshop.project_assets_name', { project: projectName }) : ''}
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
