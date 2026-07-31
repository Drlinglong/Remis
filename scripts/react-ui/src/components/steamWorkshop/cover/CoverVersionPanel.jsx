import { Alert, Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core';

const formatCreatedAt = (value) => {
    if (!value) return '';
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(new Date(value));
};

export const CoverVersionPanel = ({
    workspaceId,
    projectId,
    versions,
    selectedVersionId,
    busyAction,
    error,
    draftSavedAt,
    onSave,
    onLoad,
    onSelect,
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

            <Title order={5}>{labels.historyTitle}</Title>
            {versions.length === 0 ? (
                <Text c="dimmed" size="sm">{labels.emptyHistory}</Text>
            ) : (
                <Stack gap="xs">
                    {versions.map((version) => (
                        <Paper key={version.version_id} withBorder p="sm" data-remis-surface="paper">
                            <Group justify="space-between" align="flex-start" wrap="nowrap">
                                <div className="cover-version-copy">
                                    <Group gap="xs">
                                        <Text fw={600}>#{version.sequence}</Text>
                                        {version.version_id === selectedVersionId && (
                                            <Badge size="sm">{labels.selected}</Badge>
                                        )}
                                    </Group>
                                    <Text c="dimmed" size="xs">{formatCreatedAt(version.created_at)}</Text>
                                    <Text
                                        c="dimmed"
                                        size="xs"
                                        ff="monospace"
                                        title={version.sha256}
                                        className="cover-version-hash"
                                    >
                                        {version.sha256}
                                    </Text>
                                </div>
                                <Stack gap={4}>
                                    <Button
                                        size="compact-xs"
                                        variant="subtle"
                                        loading={busyAction === `load:${version.version_id}`}
                                        onClick={() => onLoad(version.version_id)}
                                    >
                                        {labels.loadForEditing}
                                    </Button>
                                    <Button
                                        size="compact-xs"
                                        variant="light"
                                        disabled={version.version_id === selectedVersionId}
                                        loading={busyAction === `select:${version.version_id}`}
                                        onClick={() => onSelect(version.version_id)}
                                    >
                                        {labels.useVersion}
                                    </Button>
                                </Stack>
                            </Group>
                        </Paper>
                    ))}
                </Stack>
            )}
        </Stack>
    </Paper>
);
