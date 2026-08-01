import React, { useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Center,
  Group,
  Image,
  Loader,
  Modal,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconFileDescription, IconPhoto } from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';

import { BbcodePreview } from './description/BbcodePreview';
import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../utils/localizedDateTime';
import { usePublishingVersionHistory } from './usePublishingVersionHistory';

const typeLabel = (assetType, t) => assetType === 'cover'
  ? t('steam_workshop.cover_label')
  : t('steam_workshop.description');

export default function PublishingVersionHistory({ workspaceId }) {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const history = usePublishingVersionHistory(workspaceId);
  const [deleteTarget, setDeleteTarget] = useState(null);

  if (history.isLoading) {
    return <Center h={220}><Loader type="dots" /></Center>;
  }

  return (
    <Stack gap="lg" data-remis-surface="surface">
      <div>
        <Title order={3}>{t('steam_workshop.version_history')}</Title>
        <Text c="dimmed">
          {t('steam_workshop.history_desc')}
        </Text>
      </div>

      {history.error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title={t('steam_workshop.version_operation_failed')}>
          {history.error}
        </Alert>
      )}

      <SegmentedControl
        value={history.filter}
        onChange={history.setFilter}
        data={[
          { value: 'all', label: t('steam_workshop.all_versions', { count: history.versions.length }) },
          {
            value: 'cover',
            label: t('steam_workshop.cover_versions', { count: history.versions.filter((item) => item.asset_type === 'cover').length }),
          },
          {
            value: 'description',
            label: t('steam_workshop.description_versions', { count: history.versions.filter((item) => item.asset_type === 'description').length }),
          },
        ]}
      />

      {!history.filteredVersions.length ? (
        <Alert color="blue" title={t('steam_workshop.no_matching_versions')}>
          {t('steam_workshop.no_matching_versions_desc')}
        </Alert>
      ) : (
        <Stack gap="sm">
          {history.filteredVersions.map((version) => {
            const selected = history.isSelected(version);
            const TypeIcon = version.asset_type === 'cover'
              ? IconPhoto
              : IconFileDescription;
            return (
              <Paper
                key={version.version_id}
                withBorder
                p="md"
                data-remis-surface="paper"
              >
                <Group justify="space-between" align="flex-start">
                  <Group align="flex-start">
                    <TypeIcon size={20} />
                    <div>
                      <Group gap="xs">
                        <Text fw={600}>{t('steam_workshop.asset_version', { asset: typeLabel(version.asset_type, t), sequence: version.sequence })}</Text>
                        {selected && <Badge color="green">{t('steam_workshop.adopted')}</Badge>}
                        {!selected && <Badge variant="light">{t('steam_workshop.candidate')}</Badge>}
                      </Group>
                      <Text size="xs" c="dimmed">
                        {formatLocalizedDateTime(version.created_at, getResolvedInterfaceLocale(i18n), {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })} · {version.source}
                        {version.language ? ` · ${version.language}` : ''}
                      </Text>
                    </div>
                  </Group>
                  <Group gap="xs">
                    {version.asset_type === 'cover' && (
                      <Button
                        data-remis-action="paper-secondary"
                        size="compact-sm"
                        variant="subtle"
                        onClick={() => navigate(
                          `/steam-workshop/${workspaceId}/cover?coverVersionId=${encodeURIComponent(version.version_id)}`,
                        )}
                      >
                        {t('steam_workshop.load_for_editing')}
                      </Button>
                    )}
                    <Button
                      data-remis-action="paper-secondary"
                      size="compact-sm"
                      variant="subtle"
                      onClick={() => history.setOpenedVersion(version)}
                    >
                      {t('steam_workshop.open')}
                    </Button>
                    <Button
                      data-remis-action="paper-primary"
                      size="compact-sm"
                      disabled={selected}
                      loading={history.busyVersionId === version.version_id}
                      onClick={() => history.adoptVersion(version)}
                    >
                      {selected ? t('steam_workshop.adopted') : t('steam_workshop.adopt')}
                    </Button>
                    <Button
                      data-remis-action="paper-danger"
                      size="compact-sm"
                      color="red"
                      variant="subtle"
                      disabled={selected}
                      onClick={() => setDeleteTarget(version)}
                    >
                      {selected ? t('steam_workshop.adopted_cannot_delete') : t('steam_workshop.delete')}
                    </Button>
                  </Group>
                </Group>
              </Paper>
            );
          })}
        </Stack>
      )}

      <Modal
        opened={Boolean(history.openedVersion)}
        onClose={() => history.setOpenedVersion(null)}
        data-remis-surface="elevated"
        title={history.openedVersion
          ? t('steam_workshop.asset_version', { asset: typeLabel(history.openedVersion.asset_type, t), sequence: history.openedVersion.sequence })
          : t('steam_workshop.version_content')}
        size="xl"
      >
        <Stack data-remis-surface="elevated">
          {history.openedVersion?.asset_type === 'cover' ? (
            <Image
              alt={t('steam_workshop.cover_version_alt', { sequence: history.openedVersion.sequence })}
              fit="contain"
              mah="70vh"
              src={history.openedVersion.content_url}
            />
          ) : (
            <BbcodePreview bbcode={history.openedVersion?.bbcode || ''} />
          )}
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        data-remis-surface="elevated"
        title={t('steam_workshop.delete_version')}
      >
        <Stack data-remis-surface="elevated">
          <Text>
            {deleteTarget
              ? t('steam_workshop.delete_confirmation', { asset: typeLabel(deleteTarget.asset_type, t), sequence: deleteTarget.sequence })
              : ''}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>{t('steam_workshop.cancel')}</Button>
            <Button
              color="red"
              loading={history.busyVersionId === deleteTarget?.version_id}
              onClick={async () => {
                if (deleteTarget && await history.deleteVersion(deleteTarget)) {
                  setDeleteTarget(null);
                }
              }}
            >
              {t('steam_workshop.confirm_delete')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
