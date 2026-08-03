import React from 'react';
import { Badge, Button, Group, Paper, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../../utils/localizedDateTime';

const formatTime = (value, t, language) => {
  if (!value) return t('steam_workshop.unknown_time');
  return formatLocalizedDateTime(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

export const DescriptionVersionHistory = ({
  currentVersionId,
  isSaving,
  onAdopt,
  onOpen,
  versions,
}) => {
  const { t, i18n } = useTranslation();
  return (
  <Stack gap="sm" data-remis-surface="surface">
      {versions.length === 0 && <Text c="dimmed">{t('steam_workshop.no_saved_versions')}</Text>}
      {versions.map((version) => {
        const isCurrent = version.version_id === currentVersionId;
        return (
          <Paper withBorder p="sm" key={version.version_id} data-remis-surface="paper">
            <Group justify="space-between" align="flex-start">
              <div>
                <Group gap="xs">
                  <Text fw={600}>{t('steam_workshop.version_number', { sequence: version.sequence })}</Text>
                  {isCurrent && <Badge color="green">{t('steam_workshop.adopted')}</Badge>}
                  {!isCurrent && <Badge variant="light">{t('steam_workshop.candidate')}</Badge>}
                </Group>
                <Text size="xs" c="dimmed">
                  {formatTime(version.created_at, t, getResolvedInterfaceLocale(i18n))} · {version.language} · {version.source}
                </Text>
              </div>
              <Group gap="xs">
                <Button size="compact-xs" variant="subtle" onClick={() => onOpen(version)}>
                  {t('steam_workshop.open')}
                </Button>
                {!isCurrent && (
                  <Button
                    size="compact-xs"
                    loading={isSaving}
                    onClick={() => onAdopt(version.version_id)}
                  >
                    {t('steam_workshop.adopt')}
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
};
