import React from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { useProjectGameSupport } from '../../hooks/useProjectGameSupport';
import { hasStructuredGameSupport } from '../../utils/gameSupportPolicy';
import styles from './ProjectDetailSurfaces.module.css';

const resourceEntryCount = (resource) => Math.max(0, Number(resource?.entry_count) || 0);
const isDisplayableMetadata = (value) => ['string', 'number', 'boolean'].includes(typeof value);

function Capability({ name, available, t }) {
  return (
    <Group justify="space-between" gap="sm" wrap="nowrap">
      <Text size="sm">{t(`game_support.capabilities.${name}`)}</Text>
      <Badge color={available ? 'teal' : 'gray'} variant="light">
        {t(available ? 'game_support.available' : 'game_support.unavailable')}
      </Badge>
    </Group>
  );
}

export default function ProjectGameSupportPanel({ projectId, gameId }) {
  const { t } = useTranslation();
  const { data, error, loading, retry } = useProjectGameSupport(projectId, gameId);

  if (!hasStructuredGameSupport(gameId)) return null;

  if (loading) {
    return <Card id="game-support-panel" data-remis-surface="paper" className={styles.paperPanel} withBorder>
      <Text role="status">{t('game_support.loading')}</Text>
    </Card>;
  }

  if (error) {
    return (
      <Alert
        id="game-support-panel"
        data-remis-surface="paper"
        className={styles.paperAlert}
        icon={<IconAlertTriangle size={18} />}
        title={t('game_support.unavailable_title')}
        color="yellow"
        withCloseButton={false}
      >
        <Stack gap="xs">
          <Text size="sm">{t('game_support.unavailable_description')}</Text>
          <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} onClick={retry}>
            {t('game_support.retry')}
          </Button>
        </Stack>
      </Alert>
    );
  }

  if (!data || typeof data !== 'object') return null;

  const capabilities = data.capabilities || {};
  const resources = Array.isArray(data.resources) ? data.resources : [];
  const diagnostics = Array.isArray(data.diagnostics) ? data.diagnostics : [];
  const metadata = Object.entries(data.metadata || {}).filter(([, value]) => isDisplayableMetadata(value));
  const totalEntries = resources.reduce((total, resource) => total + resourceEntryCount(resource), 0);
  const gameKey = String(data.game_id || gameId || '').toLowerCase();
  const guidanceKey = gameKey === 'surviving_mars'
    ? 'surviving_mars_csv'
    : 'independent_package';

  return (
    <Card
      id="game-support-panel"
      data-remis-surface="paper"
      className={styles.paperPanel}
      withBorder
      p="md"
    >
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <div>
            <Title order={3}>{t('game_support.title')}</Title>
            <Text size="sm" c="dimmed">
              {t(`game_name_${gameKey}`, gameKey)}
            </Text>
          </div>
          <Badge color={capabilities.runtime_verified ? 'teal' : 'yellow'} variant="light">
            {t(capabilities.runtime_verified ? 'game_support.runtime_verified' : 'game_support.runtime_unverified')}
          </Badge>
        </Group>

        <Text size="sm">{t('game_support.coverage_limit')}</Text>

        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Card data-remis-surface="paper" className={styles.paperInset} withBorder>
            <Text size="xs" c="dimmed">{t('game_support.recognized_resources')}</Text>
            <Title order={4}>{resources.length}</Title>
          </Card>
          <Card data-remis-surface="paper" className={styles.paperInset} withBorder>
            <Text size="xs" c="dimmed">{t('game_support.recognized_entries')}</Text>
            <Title order={4}>{totalEntries}</Title>
          </Card>
        </SimpleGrid>

        <Stack gap="xs">
          <Text fw={600}>{t('game_support.capabilities_title')}</Text>
          <Capability name="independent_translation_mod" available={capabilities.independent_translation_mod} t={t} />
          <Capability name="paradox_deployment" available={capabilities.paradox_deployment} t={t} />
          <Capability name="source_cleanup" available={capabilities.source_cleanup} t={t} />
          <Text size="xs" c="dimmed">
            {t('game_support.coverage_kind')}: {' '}
            {t(`game_support.coverage_kind_${capabilities.coverage_kind}`, capabilities.coverage_kind || 'unknown')}
          </Text>
        </Stack>

        <Alert data-remis-surface="paper" className={styles.paperAlert} title={t('game_support.export_guidance_title')}>
          {t(`game_support.export_guidance.${guidanceKey}`)}
        </Alert>

        {resources.length > 0 && (
          <Stack gap="xs">
            <Text fw={600}>{t('game_support.resource_list_title')}</Text>
            {resources.map((resource, index) => (
              <Group key={`${resource.path || 'resource'}-${index}`} justify="space-between" gap="sm" wrap="wrap">
                <Text size="sm" style={{ overflowWrap: 'anywhere' }}>{resource.path || t('game_support.path_unknown')}</Text>
                <Badge variant="outline">{t('game_support.resource_entry_count', { count: resourceEntryCount(resource) })}</Badge>
              </Group>
            ))}
          </Stack>
        )}

        {diagnostics.length > 0 ? (
          <Stack gap="xs">
            <Text fw={600}>{t('game_support.diagnostics_title')}</Text>
            {diagnostics.map((diagnostic, index) => (
              <Alert
                key={`${diagnostic.code || 'diagnostic'}-${diagnostic.path || index}`}
                data-remis-surface="paper"
                className={styles.paperAlert}
                color={diagnostic.severity === 'error' ? 'red' : 'yellow'}
                title={t(`game_support.diagnostics.${diagnostic.code}`, diagnostic.message || diagnostic.code)}
              >
                {diagnostic.path && <Text size="xs" style={{ overflowWrap: 'anywhere' }}>{diagnostic.path}</Text>}
              </Alert>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">{t('game_support.no_unsupported_diagnostics')}</Text>
        )}

        {metadata.length > 0 && (
          <details>
            <summary>
              <Text component="span" fw={600}>{t('game_support.metadata_title')}</Text>
            </summary>
            <Stack gap="xs" mt="xs">
            {metadata.map(([key, value]) => (
              <Group key={key} justify="space-between" gap="sm" wrap="wrap">
                <Text size="sm">{key}</Text>
                <Text size="sm" c="dimmed">{String(value)}</Text>
              </Group>
            ))}
            </Stack>
          </details>
        )}
      </Stack>
    </Card>
  );
}
