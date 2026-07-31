import React from 'react';
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

import { BbcodePreview } from './description/BbcodePreview';
import { usePublishingVersionHistory } from './usePublishingVersionHistory';

const formatTime = (value) => new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(new Date(value));

const typeLabel = (assetType) => assetType === 'cover' ? '封面图' : '工坊描述';

export default function PublishingVersionHistory({ workspaceId }) {
  const history = usePublishingVersionHistory(workspaceId);

  if (history.isLoading) {
    return <Center h={220}><Loader type="dots" /></Center>;
  }

  return (
    <Stack gap="lg" data-remis-surface="surface">
      <div>
        <Title order={3}>版本历史</Title>
        <Text c="dimmed">
          封面图和工坊描述的候选版本统一保存在这里；“打开”只检视内容，“设为采用”才会更新当前版本。
        </Text>
      </div>

      {history.error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="版本操作失败">
          {history.error}
        </Alert>
      )}

      <SegmentedControl
        value={history.filter}
        onChange={history.setFilter}
        data={[
          { value: 'all', label: `全部 (${history.versions.length})` },
          {
            value: 'cover',
            label: `封面图 (${history.versions.filter((item) => item.asset_type === 'cover').length})`,
          },
          {
            value: 'description',
            label: `工坊描述 (${history.versions.filter((item) => item.asset_type === 'description').length})`,
          },
        ]}
      />

      {!history.filteredVersions.length ? (
        <Alert color="blue" title="还没有匹配的版本">
          在封面图或工坊描述页面保存候选版本后，它会出现在这里。
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
                        <Text fw={600}>{typeLabel(version.asset_type)} #{version.sequence}</Text>
                        {selected && <Badge color="green">当前采用</Badge>}
                        {!selected && <Badge variant="light">候选</Badge>}
                      </Group>
                      <Text size="xs" c="dimmed">
                        {formatTime(version.created_at)} · {version.source}
                        {version.language ? ` · ${version.language}` : ''}
                      </Text>
                    </div>
                  </Group>
                  <Group gap="xs">
                    <Button
                      data-remis-action="paper-secondary"
                      size="compact-sm"
                      variant="subtle"
                      onClick={() => history.setOpenedVersion(version)}
                    >
                      打开
                    </Button>
                    <Button
                      data-remis-action="paper-primary"
                      size="compact-sm"
                      disabled={selected}
                      loading={history.busyVersionId === version.version_id}
                      onClick={() => history.adoptVersion(version)}
                    >
                      {selected ? '当前采用' : '设为采用'}
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
        title={history.openedVersion
          ? `${typeLabel(history.openedVersion.asset_type)} #${history.openedVersion.sequence}`
          : '版本内容'}
        size="xl"
      >
        <Stack data-remis-surface="elevated">
          {history.openedVersion?.asset_type === 'cover' ? (
            <Image
              alt={`封面图版本 ${history.openedVersion.sequence}`}
              fit="contain"
              mah="70vh"
              src={history.openedVersion.content_url}
            />
          ) : (
            <BbcodePreview bbcode={history.openedVersion?.bbcode || ''} />
          )}
        </Stack>
      </Modal>
    </Stack>
  );
}
