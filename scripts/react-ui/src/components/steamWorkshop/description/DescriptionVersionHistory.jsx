import React from 'react';
import { Badge, Button, Group, Paper, Stack, Text } from '@mantine/core';

const formatTime = (value) => {
  if (!value) return '未知时间';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
};

export const DescriptionVersionHistory = ({
  currentVersionId,
  isSaving,
  onAdopt,
  onOpen,
  versions,
}) => (
  <Stack gap="sm" data-remis-surface="surface">
      {versions.length === 0 && <Text c="dimmed">还没有已保存版本。</Text>}
      {versions.map((version) => {
        const isCurrent = version.version_id === currentVersionId;
        return (
          <Paper withBorder p="sm" key={version.version_id} data-remis-surface="paper">
            <Group justify="space-between" align="flex-start">
              <div>
                <Group gap="xs">
                  <Text fw={600}>版本 {version.sequence}</Text>
                  {isCurrent && <Badge color="green">当前采用</Badge>}
                  {!isCurrent && <Badge variant="light">候选</Badge>}
                </Group>
                <Text size="xs" c="dimmed">
                  {formatTime(version.created_at)} · {version.language} · {version.source}
                </Text>
              </div>
              <Group gap="xs">
                <Button size="compact-xs" variant="subtle" onClick={() => onOpen(version)}>
                  打开
                </Button>
                {!isCurrent && (
                  <Button
                    size="compact-xs"
                    loading={isSaving}
                    onClick={() => onAdopt(version.version_id)}
                  >
                    设为采用
                  </Button>
                )}
              </Group>
            </Group>
            <Text size="xs" c="dimmed" mt="xs" lineClamp={2}>
              {version.bbcode}
            </Text>
          </Paper>
        );
      })}
  </Stack>
);
