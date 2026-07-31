import { Alert, Button, Paper, Stack, Text, Title } from '@mantine/core';

export const CoverVersionPanel = ({
    workspaceId,
    projectId,
    busyAction,
    error,
    draftSavedAt,
    onSave,
    canSave,
    labels,
}) => (
    <Paper withBorder p="md" data-remis-surface="paper" className="cover-version-panel">
        <Stack gap="sm">
            <div>
                <Title order={4}>{labels.versionTitle}</Title>
                <Text c="dimmed" size="sm">
                    {workspaceId
                        ? labels.workspaceContext.replace('{id}', workspaceId)
                        : projectId
                            ? labels.projectDraft.replace('{id}', projectId)
                            : labels.unboundDraft}
                </Text>
                {draftSavedAt && (
                    <Text c="dimmed" size="xs">
                        {labels.draftSaved.replace('{time}', draftSavedAt.toLocaleTimeString())}
                    </Text>
                )}
            </div>

            {error && <Alert color="red">{labels.requestFailed}</Alert>}

            <Button onClick={onSave} loading={busyAction === 'save'} disabled={!workspaceId || !canSave}>
                {labels.saveCandidate}
            </Button>
            {!workspaceId && <Text c="dimmed" size="xs">{labels.workspaceRequired}</Text>}
            <Text c="dimmed" size="xs">已保存版本请前往独立的“版本历史”页面检视和采用。</Text>
        </Stack>
    </Paper>
);
