import React from 'react';
import {
  Alert, Badge, Button, Card, Group, Modal, Progress, Stack, Text,
} from '@mantine/core';

const ACTIVE_STATUSES = new Set([
  'queued', 'pending', 'running', 'discovering', 'scanning', 'indexing', 'activating',
]);

const asNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
};

const progressPercent = (progress = {}) => {
  if (Number.isFinite(Number(progress.percent))) return Math.max(0, Math.min(100, Number(progress.percent)));
  const total = asNumber(progress.total_files || progress.total);
  const current = asNumber(progress.processed_files || progress.files_current || progress.current);
  return total > 0 ? Math.round((current / total) * 100) : 0;
};

const gameProgressEntries = (progress = {}) => {
  const perGame = progress.per_game || progress.games || [];
  if (Array.isArray(perGame)) return perGame;
  return Object.entries(perGame).map(([gameId, value]) => ({ game_id: gameId, ...value }));
};

const stageKey = (stage) => {
  const normalized = String(stage || 'queued').toLowerCase();
  return ['discovering', 'scanning', 'indexing', 'activating', 'deleting', 'queued', 'completed', 'failed', 'partial_failed']
    .includes(normalized) ? normalized : 'running';
};

const STAGE_TRANSLATION_KEYS = {
  discovering: 'settings_reference_stage_discovering',
  scanning: 'settings_reference_stage_scanning',
  indexing: 'settings_reference_stage_indexing',
  activating: 'settings_reference_stage_activating',
  deleting: 'settings_reference_delete_confirm',
  queued: 'settings_reference_stage_queued',
  completed: 'settings_reference_stage_completed',
  failed: 'settings_reference_stage_failed',
  partial_failed: 'settings_reference_task_failed',
  running: 'settings_reference_stage_running',
};

const stageLabel = (t, stage) => t(STAGE_TRANSLATION_KEYS[stageKey(stage)]);

export default function ReferenceLibraryTaskModal({ t, opened, task, onClose }) {
  const progress = task?.progress || {};
  const games = gameProgressEntries(progress);
  const status = task?.status || 'queued';
  const active = ACTIVE_STATUSES.has(status);
  const percent = progressPercent(progress);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('settings_reference_task_title')}
      centered
      size="lg"
      closeOnClickOutside={!active}
    >
      <Stack gap="md">
        {active && (
          <Alert color="blue">
            <Text size="sm" style={{ whiteSpace: 'pre-line' }}>
              {t('settings_reference_task_background_notice')}
            </Text>
          </Alert>
        )}
        {(status === 'failed' || status === 'partial_failed') && (
          <Alert color="red" title={t('settings_reference_task_failed')}>
            {task.error || task.message || t('settings_reference_task_failed')}
          </Alert>
        )}
        <Group justify="space-between">
          <Text fw={600}>{t('settings_reference_overall_progress')}</Text>
          <Text size="sm" c="dimmed">{percent}%</Text>
        </Group>
        <Progress value={percent} aria-label={t('settings_reference_overall_progress')} />
        {games.length === 0 ? (
          <Text size="sm" c="dimmed">{stageLabel(t, progress.stage || status)}</Text>
        ) : (
          <Stack gap="xs">
            {games.map((game) => {
              const gameStatus = game.status || 'queued';
              const gamePercent = progressPercent(game);
              const currentFiles = asNumber(game.processed_files || game.files_current || game.current_files || game.current);
              const totalFiles = asNumber(game.total_files || game.files_total || game.total);
              const entries = asNumber(game.indexed_entries || game.entries_current || game.entries || game.entry_count);
              return (
                <Card key={game.game_id || game.game_name} withBorder padding="sm">
                  <Stack gap={5}>
                    <Group justify="space-between" wrap="nowrap">
                      <Text size="sm" fw={600}>{game.game_name || game.game_id}</Text>
                      <Badge color={gameStatus === 'completed' ? 'green' : gameStatus === 'failed' ? 'red' : 'blue'}>
                        {stageLabel(t, game.stage || gameStatus)}
                      </Badge>
                    </Group>
                    {game.localization_path && (
                      <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                        {game.localization_path}
                      </Text>
                    )}
                    <Progress value={gamePercent} size="sm" aria-label={`${game.game_name || game.game_id} ${gamePercent}%`} />
                    {task?.operation !== 'delete' && (
                      <Text size="xs" c="dimmed">
                        {totalFiles > 0
                          ? t('settings_reference_files_progress', { current: currentFiles, total: totalFiles })
                          : t('settings_reference_files_scanned', { count: currentFiles })}
                        {entries > 0 && ` · ${t('settings_reference_entries', { count: entries })}`}
                      </Text>
                    )}
                    {game.current_file && <Text size="xs" truncate>{game.current_file}</Text>}
                    {game.error && (
                      <Alert color="red" py="xs">
                        {game.error}
                      </Alert>
                    )}
                  </Stack>
                </Card>
              );
            })}
          </Stack>
        )}
        <Group justify="flex-end">
          <Button onClick={onClose}>{t('button_close')}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
