import React from 'react';
import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconChevronDown,
  IconDownload,
  IconBrandGithub,
  IconRefresh,
} from '@tabler/icons-react';
import { openExternalUrl } from '../../utils/externalLinks';

const COMMUNITY_RESULTS_ISSUE = 'https://github.com/Drlinglong/Remis/issues/153';

const resultRows = (run) => (
  run.results?.contestants
  || run.results
  || run.contestants
  || []
);

export default function ArenaResults({
  t,
  run,
  onPreviewExport,
  onRetryFailures,
  retrying,
}) {
  const rows = Array.isArray(resultRows(run)) ? resultRows(run) : [];
  const decisiveTotal = rows.reduce((total, row) => total + Number(
    row.selected_count ?? row.preference_count ?? row.win_count ?? row.wins ?? 0,
  ), 0);

  return (
    <Stack gap="lg">
      <Group
        className="model-arena-results-header"
        justify="space-between"
        align="flex-start"
      >
        <div>
          <Title order={3}>{t('model_arena.results_title')}</Title>
          <Text className="model-arena-results-description" c="dimmed">
            {t('model_arena.results_description')}
          </Text>
        </div>
        <Group className="model-arena-results-actions" gap="sm" justify="flex-end">
          <Button
            className="model-arena-share-invite"
            leftSection={<IconBrandGithub size={20} stroke={2.1} />}
            onClick={() => openExternalUrl(COMMUNITY_RESULTS_ISSUE)}
          >
            {t('model_arena.share_invite')}
          </Button>
          <Button leftSection={<IconDownload size={17} />} onClick={() => onPreviewExport(run)}>
            {t('model_arena.export_preview')}
          </Button>
        </Group>
      </Group>

      {run.status === 'partial_failed' && (
        <Alert
          color="yellow"
          icon={<IconAlertTriangle size={18} />}
          title={t('model_arena.partial_failed')}
        >
          <Group justify="space-between">
            <Text size="sm">{t('model_arena.partial_failed_description')}</Text>
            <Button
              variant="light"
              color="yellow"
              leftSection={<IconRefresh size={16} />}
              onClick={onRetryFailures}
              loading={retrying}
            >
              {t('model_arena.retry_failures')}
            </Button>
          </Group>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, md: Math.min(3, rows.length || 2) }}>
        {rows.map((row) => {
          const wins = Number(
            row.selected_count ?? row.preference_count ?? row.win_count ?? row.wins ?? 0,
          );
          const preferenceRate = row.preference_rate == null
            ? (decisiveTotal ? wins / decisiveTotal : 0)
            : Number(row.preference_rate);
          const reasonCounts = row.reason_counts || row.reasons || {};
          return (
            <Card
              key={row.contestant_id || `${row.provider_id}:${row.model_id}`}
              className="model-arena-result-card"
              data-remis-surface="paper"
              withBorder
              radius="md"
              padding="lg"
            >
              <Stack gap="md">
                <div>
                  <Badge
                    className="model-arena-provider-badge"
                    size="lg"
                    variant="filled"
                    mb="xs"
                  >
                    {row.provider_name || row.provider_id}
                  </Badge>
                  <Title order={3} className="model-arena-model-name">
                    {row.model_name || row.model_id}
                  </Title>
                </div>
                <Group grow>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.wins')}</Text>
                    <Text fw={800} size="xl">{wins}</Text>
                  </div>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.preference_rate')}</Text>
                    <Text fw={800} size="xl">{Math.round(preferenceRate * 100)}%</Text>
                  </div>
                </Group>
                <Progress value={preferenceRate * 100} />
                <SimpleGrid cols={2}>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.hard_errors')}</Text>
                    <Text fw={700}>{row.hard_error_occurrences ?? row.hard_error_count ?? 0}</Text>
                  </div>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.affected_samples')}</Text>
                    <Text fw={700}>{row.affected_sample_count ?? 0}</Text>
                  </div>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.requests')}</Text>
                    <Text fw={700}>{row.request_count ?? '—'}</Text>
                  </div>
                  <div>
                    <Text size="xs" c="dimmed">{t('model_arena.elapsed')}</Text>
                    <Text fw={700}>{row.elapsed_ms == null ? '—' : `${Math.round(row.elapsed_ms / 100) / 10}s`}</Text>
                  </div>
                </SimpleGrid>
                {Object.keys(reasonCounts).length > 0 && (
                  <div>
                    <Text size="xs" fw={700} c="dimmed" mb="xs">{t('model_arena.reason_summary')}</Text>
                    <Group gap="xs">
                      {Object.entries(reasonCounts).map(([reason, count]) => (
                        <Badge key={reason} variant="light">
                          {t(`model_arena.reason_${reason}`, { defaultValue: reason })}: {count}
                        </Badge>
                      ))}
                    </Group>
                  </div>
                )}
                {row.failure_code && <Badge color="red">{row.failure_code}</Badge>}
              </Stack>
            </Card>
          );
        })}
      </SimpleGrid>

      <Group>
        <Badge variant="outline">
          {t('model_arena.tie_count', { count: run.results?.tie_count ?? run.tie_count ?? 0 })}
        </Badge>
        <Badge variant="outline">
          {t('model_arena.reject_count', { count: run.results?.reject_all_count ?? run.reject_all_count ?? 0 })}
        </Badge>
      </Group>

      <div>
        <Title order={4} mb="md">{t('model_arena.output_review_title')}</Title>
        <Accordion
          variant="separated"
          chevron={<IconChevronDown size={18} />}
          className="model-arena-output-review"
        >
          {(run.samples || []).map((sample, index) => {
            const ordinal = Number.isInteger(sample.ordinal)
              ? sample.ordinal + 1
              : index + 1;
            return (
              <Accordion.Item
                key={`sample-${sample.sample_id}`}
                value={sample.sample_id}
                data-remis-surface="paper"
              >
                <Accordion.Control>
                  <Text fw={800}>
                    {t('model_arena.output_sample', { number: ordinal })}
                  </Text>
                  <Text size="sm" c="dimmed" lineClamp={1} mt={2}>
                    {sample.source_text}
                  </Text>
                </Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <Card data-remis-surface="paper" withBorder radius="sm" padding="md">
                      <Text size="xs" fw={700} c="dimmed">
                        {t('model_arena.source_text')}
                      </Text>
                      <Text mt={4}>{sample.source_text}</Text>
                    </Card>
                    {rows.map((row) => {
                      const contestantId = row.contestant_id;
                      const output = (sample.outputs || []).find(
                        (item) => item.contestant_id === contestantId,
                      );
                      return (
                      <Card
                        key={`${sample.sample_id}-${contestantId}`}
                        data-remis-surface="paper"
                        withBorder
                        radius="sm"
                        padding="md"
                      >
                        <Group gap="xs">
                          <Badge variant="filled">
                            {row.provider_name || row.provider_id}
                          </Badge>
                          <Text fw={800}>{row.model_name || row.model_id}</Text>
                        </Group>
                        <Text mt={4}>
                          {output?.translated_text || t('model_arena.unavailable_output')}
                        </Text>
                      </Card>
                      );
                    })}
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            );
          })}
        </Accordion>
      </div>
    </Stack>
  );
}
