import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Select,
  Stack,
  Text,
} from '@mantine/core';
import { open } from '@tauri-apps/plugin-dialog';
import { IconDatabase, IconFolderOpen, IconRefresh } from '@tabler/icons-react';

import api from '../../utils/api';


export default function ReferenceLibraryMaintenanceCard({ t }) {
  const [libraries, setLibraries] = useState([]);
  const [selectedGameId, setSelectedGameId] = useState('victoria3');
  const [busyAction, setBusyAction] = useState('');
  const [message, setMessage] = useState(null);

  const refresh = useCallback(async () => {
    const response = await api.get('/api/system/reference-library');
    setLibraries(response.data?.libraries || []);
  }, []);

  useEffect(() => {
    refresh().catch((error) => {
      setMessage({ color: 'red', text: error?.response?.data?.detail || error.message });
    });
  }, [refresh]);

  const gameOptions = useMemo(() => libraries.map((library) => ({
    value: library.game_id,
    label: library.game_name,
  })), [libraries]);

  const runAction = async (name, action) => {
    setBusyAction(name);
    setMessage(null);
    try {
      const response = await action();
      await refresh();
      const builtCount = response.data?.built?.length;
      setMessage({
        color: 'green',
        text: builtCount === 0
          ? t('settings_reference_none_found')
          : t('settings_reference_build_success', { count: builtCount || 1 }),
      });
    } catch (error) {
      setMessage({
        color: 'red',
        text: error?.response?.data?.detail || error.message || t('notification.error_generic'),
      });
    } finally {
      setBusyAction('');
    }
  };

  const autoBuild = () => runAction(
    'auto',
    () => api.post('/api/system/reference-library/auto-build'),
  );

  const manualBuild = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: t('settings_reference_manual_picker'),
    });
    if (!selected || typeof selected !== 'string') return;
    await runAction(
      'manual',
      () => api.post('/api/system/reference-library/build', {
        game_id: selectedGameId,
        localization_path: selected,
      }),
    );
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
            loading={busyAction === 'auto'}
            disabled={Boolean(busyAction)}
            onClick={autoBuild}
          >
            {t('settings_reference_auto_build')}
          </Button>
        </Group>

        {message && <Alert color={message.color}>{message.text}</Alert>}

        <Stack gap="xs">
          {libraries.map((library) => (
            <Card key={library.game_id} withBorder padding="sm" radius="sm">
              <Group justify="space-between" align="flex-start">
                <div>
                  <Group gap="xs">
                    <Text size="sm" fw={600}>{library.game_name}</Text>
                    <Badge color={library.available ? (library.stale ? 'orange' : 'green') : 'gray'}>
                      {t(library.available
                        ? (library.stale ? 'settings_reference_stale' : 'settings_reference_ready')
                        : 'settings_reference_missing')}
                    </Badge>
                  </Group>
                  {library.available && (
                    <Stack gap={2} mt={4}>
                      <Text size="xs" c="dimmed">
                        {t('settings_reference_version')}: {library.game_version} ·{' '}
                        {t('settings_reference_entries', { count: library.entry_count })}
                      </Text>
                      <Code fz="xs">{library.root_path}</Code>
                    </Stack>
                  )}
                </div>
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
            loading={busyAction === 'manual'}
            disabled={Boolean(busyAction) || !selectedGameId}
            onClick={manualBuild}
          >
            {t('settings_reference_manual_build')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed">{t('settings_reference_manual_hint')}</Text>
      </Stack>
    </Card>
  );
}
