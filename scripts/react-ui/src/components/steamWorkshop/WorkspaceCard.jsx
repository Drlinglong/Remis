import React from 'react';
import { Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { IconArrowRight, IconEdit } from '@tabler/icons-react';

import styles from './SteamWorkshopOverview.module.css';

const formatTime = (value) => {
  if (!value) return '尚未更新';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
};

const VersionSummary = ({ current, count, label }) => (
  <Paper withBorder p="sm" data-remis-surface="paper">
    <Text size="xs" c="dimmed">{label}</Text>
    <Text fw={600}>
      {current ? `当前采用 #${current.sequence}` : '尚未采用版本'}
    </Text>
    <Text size="xs" c="dimmed">{count} 个候选与历史版本</Text>
  </Paper>
);

export default function WorkspaceCard({ onEdit, onOpen, projectName, workspace }) {
  return (
    <Paper withBorder p="lg" data-remis-surface="paper" className={styles.card}>
      <Stack gap="md" className={styles.metadata}>
        <div>
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Title order={3} className={styles.cardTitle} title={workspace.name}>
              {workspace.name}
            </Title>
            <Button
              aria-label={`编辑 ${workspace.name}`}
              data-remis-action="paper-secondary"
              size="compact-sm"
              variant="subtle"
              onClick={() => onEdit(workspace)}
            >
              <IconEdit size={16} />
            </Button>
          </Group>
          <Group gap="xs" mt="xs">
            <Badge variant="light">
              {workspace.project_id ? `项目：${projectName || workspace.project_id}` : '独立工作区'}
            </Badge>
            <Badge variant="outline">
              {workspace.workshop_item_id
                ? `Workshop ID: ${workspace.workshop_item_id}`
                : '未绑定 Workshop ID'}
            </Badge>
          </Group>
        </div>

        <div className={styles.versionGrid}>
          <VersionSummary
            current={workspace.current_cover_version}
            count={workspace.cover_version_count}
            label="封面图"
          />
          <VersionSummary
            current={workspace.current_description_version}
            count={workspace.description_version_count}
            label="工坊描述"
          />
        </div>

        <Text size="xs" c="dimmed">
          最近更新：{formatTime(workspace.updated_at)}
        </Text>
      </Stack>
      <Button
        data-remis-action="paper-primary"
        mt="lg"
        rightSection={<IconArrowRight size={16} />}
        onClick={() => onOpen(workspace.workspace_id)}
      >
        进入工作区
      </Button>
    </Paper>
  );
}
