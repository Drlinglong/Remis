import React from 'react';
import { Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { IconArrowRight, IconEdit } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../utils/localizedDateTime';
import styles from './SteamWorkshopOverview.module.css';

const formatTime = (value, t, language) => {
  if (!value) return t('steam_workshop.not_updated');
  return formatLocalizedDateTime(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const VersionSummary = ({ current, count, label, t }) => (
  <Paper withBorder p="sm" data-remis-surface="paper">
    <Text size="xs" c="dimmed">{label}</Text>
    <Text fw={600}>
      {current ? t('steam_workshop.adopted_version', { sequence: current.sequence }) : t('steam_workshop.no_adopted_version')}
    </Text>
    <Text size="xs" c="dimmed">{t('steam_workshop.candidates_count', { count })}</Text>
  </Paper>
);

export default function WorkspaceCard({ onEdit, onOpen, projectName, workspace }) {
  const { t, i18n } = useTranslation();
  return (
    <Paper withBorder p="lg" data-remis-surface="paper" className={styles.card}>
      <Stack gap="md" className={styles.metadata}>
        <div>
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Title order={3} className={styles.cardTitle} title={workspace.name}>
              {workspace.name}
            </Title>
            <Button
              aria-label={t('steam_workshop.edit_workspace_name', { name: workspace.name })}
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
              {workspace.project_id
                ? t('steam_workshop.project_context', { project: projectName || workspace.project_id })
                : t('steam_workshop.independent_workspace')}
            </Badge>
            <Badge variant="outline">
              {workspace.workshop_item_id
                ? `Workshop ID: ${workspace.workshop_item_id}`
                : t('steam_workshop.workshop_id_unbound')}
            </Badge>
          </Group>
        </div>

        <div className={styles.versionGrid}>
          <VersionSummary
            current={workspace.current_cover_version}
            count={workspace.cover_version_count}
            label={t('steam_workshop.cover_label')}
            t={t}
          />
          <VersionSummary
            current={workspace.current_description_version}
            count={workspace.description_version_count}
            label={t('steam_workshop.description')}
            t={t}
          />
        </div>

        <Text size="xs" c="dimmed">
          {t('steam_workshop.latest_update', { time: formatTime(workspace.updated_at, t, getResolvedInterfaceLocale(i18n)) })}
        </Text>
      </Stack>
      <Button
        data-remis-action="paper-primary"
        mt="lg"
        rightSection={<IconArrowRight size={16} />}
        onClick={() => onOpen(workspace.workspace_id)}
      >
        {t('steam_workshop.enter_workspace')}
      </Button>
    </Paper>
  );
}
