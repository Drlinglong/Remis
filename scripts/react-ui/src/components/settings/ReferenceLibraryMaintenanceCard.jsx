import React, { useMemo, useState } from 'react';
import {
  Alert, Badge, Button, Card, Code, Group, Select, Stack, Text,
} from '@mantine/core';
import { open } from '@tauri-apps/plugin-dialog';
import { IconDatabase, IconFolderOpen, IconRefresh, IconTrash } from '@tabler/icons-react';

import ReferenceLibraryDeleteModal from './ReferenceLibraryDeleteModal';
import ReferenceLibraryDiscoveryModal from './ReferenceLibraryDiscoveryModal';
import ReferenceLibraryTaskModal from './ReferenceLibraryTaskModal';
import useReferenceLibraryMaintenance, {
  referenceLibraryTaskIsActive,
} from '../../hooks/useReferenceLibraryMaintenance';

const statusKey = (library) => (
  library.available ? (library.stale ? 'settings_reference_stale' : 'settings_reference_ready')
    : 'settings_reference_missing'
);

export default function ReferenceLibraryMaintenanceCard({ t }) {
  const [selectedGameId, setSelectedGameId] = useState('victoria3');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const {
    libraries,
    candidates,
    selectedIds,
    task,
    discoveryOpen,
    taskOpen,
    loading,
    error,
    setDiscoveryOpen,
    setTaskOpen,
    toggleCandidate,
    openDiscovery,
    confirmDiscovery,
    deleteLibrary,
  } = useReferenceLibraryMaintenance();
  const taskActive = referenceLibraryTaskIsActive(task);

  const gameOptions = useMemo(() => libraries.map((library) => ({
    value: library.game_id,
    label: library.game_name,
  })), [libraries]);

  const handleManualBuild = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: t('settings_reference_manual_picker'),
    });
    if (!selected || typeof selected !== 'string') return;
    await openDiscovery({
      game_id: selectedGameId,
      game_name: libraries.find((library) => library.game_id === selectedGameId)?.game_name
        || selectedGameId,
      localization_path: selected,
      status: 'missing',
    });
  };

  const handleUpdate = (library) => openDiscovery({
    ...library,
    localization_path: library.root_path || library.localization_path,
    status: 'stale',
  });

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteLibrary(deleteTarget.game_id);
    setDeleteTarget(null);
  };

  return (
    <Card withBorder p="lg" radius="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Group align="flex-start" wrap="nowrap">
            <IconDatabase size={22} />
            <div>
              <Text fw={600}>{t('settings_reference_title')}</Text>
              <Text size="sm" c="dimmed" maw={720}>{t('settings_reference_desc')}</Text>
            </div>
          </Group>
          <Button
            leftSection={<IconRefresh size={16} />}
            loading={loading}
            disabled={loading || taskActive}
            onClick={() => openDiscovery()}
          >
            {t('settings_reference_auto_build')}
          </Button>
        </Group>

        {error && <Alert color="red">{error}</Alert>}
        {taskActive && (
          <Alert color="blue">
            {t('settings_reference_task_running')}
            <Button variant="subtle" size="compact-sm" ml="xs" onClick={() => setTaskOpen(true)}>
              {t('settings_reference_view_progress')}
            </Button>
          </Alert>
        )}

        <Stack gap="xs">
          {libraries.map((library) => (
            <Card key={library.game_id} withBorder padding="sm" radius="sm">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <div style={{ minWidth: 0 }}>
                  <Group gap="xs">
                    <Text size="sm" fw={600}>{library.game_name}</Text>
                    <Badge color={library.available ? (library.stale ? 'orange' : 'green') : 'gray'}>
                      {t(statusKey(library))}
                    </Badge>
                  </Group>
                  <Stack gap={2} mt={4}>
                    {library.game_version && (
                      <Text size="xs" c="dimmed">
                        {t('settings_reference_version')}: {library.game_version}
                        {library.entry_count != null && ` · ${t('settings_reference_entries', { count: library.entry_count })}`}
                      </Text>
                    )}
                    {(library.root_path || library.localization_path) && (
                      <Code fz="xs" style={{ whiteSpace: 'normal', wordBreak: 'break-all' }}>
                        {library.root_path || library.localization_path}
                      </Code>
                    )}
                  </Stack>
                </div>
                {library.available && (
                  <Group gap="xs" wrap="nowrap">
                    <Button size="compact-sm" variant="light" disabled={taskActive} onClick={() => handleUpdate(library)}>
                      {t('settings_reference_update')}
                    </Button>
                    <Button
                      size="compact-sm"
                      variant="subtle"
                      color="red"
                      disabled={taskActive}
                      aria-label={t('settings_reference_delete_for', { game: library.game_name })}
                      onClick={() => setDeleteTarget(library)}
                    >
                      <IconTrash size={16} />
                    </Button>
                  </Group>
                )}
              </Group>
            </Card>
          ))}
        </Stack>

        <Group align="flex-end">
          <Select
            label={t('settings_reference_game')}
            value={selectedGameId}
            onChange={setSelectedGameId}
            data={gameOptions}
            flex={1}
          />
          <Button
            variant="light"
            leftSection={<IconFolderOpen size={16} />}
            loading={loading}
            disabled={loading || taskActive || !selectedGameId}
            onClick={handleManualBuild}
          >
            {t('settings_reference_manual_build')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed">{t('settings_reference_manual_hint')}</Text>
      </Stack>

      <ReferenceLibraryDiscoveryModal
        t={t}
        opened={discoveryOpen}
        candidates={candidates}
        selectedIds={selectedIds}
        loading={loading}
        onToggle={toggleCandidate}
        onConfirm={confirmDiscovery}
        onClose={() => setDiscoveryOpen(false)}
      />
      <ReferenceLibraryTaskModal
        t={t}
        opened={taskOpen}
        task={task}
        onClose={() => setTaskOpen(false)}
      />
      <ReferenceLibraryDeleteModal
        t={t}
        opened={Boolean(deleteTarget)}
        game={deleteTarget}
        loading={loading}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
      />
    </Card>
  );
}
