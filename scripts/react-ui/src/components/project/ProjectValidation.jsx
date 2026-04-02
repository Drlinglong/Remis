import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Badge, Button, Card, Group, Loader, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconInfoCircle, IconRefresh, IconRobot } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import api from '../../utils/api';
import { useTranslation } from 'react-i18next';

const ProjectValidation = ({ projectId }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const localizeIssueLabel = useCallback((code) => {
    if (!code) return t('agent_workshop.unknown_issue');
    const key = String(code).trim();
    const known = {
      validation_vic3_variable_parity_mismatch: t('agent_workshop.issue_vic3_variable_parity'),
      validation_vic3_color_tags_mismatch: t('agent_workshop.issue_vic3_color_tags'),
      validation_invalid_key_format: t('agent_workshop.issue_invalid_key_format'),
      'Invalid key format': t('agent_workshop.issue_invalid_key_format'),
    };
    if (known[key]) return known[key];
    if (key.startsWith('validation_')) {
      return t('agent_workshop.issue_validation_generic');
    }
    return key;
  }, [t]);

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/project/${projectId}/validation-status`);
      setStatus(res.data || null);
    } catch (error) {
      console.error('Failed to load validation status', error);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const refreshSidecar = async () => {
    try {
      setRefreshing(true);
      await api.get(`/api/agent-workshop/scan?project_id=${projectId}&force=true`);
      await loadStatus();
    } catch (error) {
      console.error('Failed to refresh workshop sidecar', error);
    } finally {
      setRefreshing(false);
    }
  };

  const openWorkshop = () => {
    navigate('/agent-workshop', { state: { projectId } });
  };

  const entries = useMemo(
    () => Object.entries(status?.issue_type_counts || {}).sort((a, b) => b[1] - a[1]),
    [status]
  );

  if (loading) {
    return (
      <Paper withBorder p="lg" radius="md">
        <Group justify="center">
          <Loader size="sm" />
        </Group>
      </Paper>
    );
  }

  return (
    <Stack p="md" gap="lg">
      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="md">
          <Stack gap={0}>
            <Title order={4}>{t('project_validation.title')}</Title>
            <Text size="xs" c="dimmed">
              {t('project_validation.subtitle')}
            </Text>
          </Stack>
          <Group>
            <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={refreshSidecar} loading={refreshing}>
              {t('project_validation.refresh')}
            </Button>
            <Button leftSection={<IconRobot size={16} />} onClick={openWorkshop}>
              {t('project_validation.open_workshop')}
            </Button>
          </Group>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} mb="md">
          <Card withBorder p="sm" radius="md">
            <Text size="xs" c="dimmed">{t('project_validation.issues_count')}</Text>
            <Text size="lg" fw={700}>{status?.issues_count ?? 0}</Text>
          </Card>
          <Card withBorder p="sm" radius="md">
            <Text size="xs" c="dimmed">{t('project_validation.last_updated')}</Text>
            <Text size="sm" fw={600}>{status?.last_updated_at ? new Date(status.last_updated_at).toLocaleString() : '--'}</Text>
          </Card>
          <Card withBorder p="sm" radius="md">
            <Text size="xs" c="dimmed">{t('project_validation.report_count')}</Text>
            <Text size="lg" fw={700}>{status?.report_count ?? 0}</Text>
          </Card>
          <Card withBorder p="sm" radius="md">
            <Text size="xs" c="dimmed">{t('project_validation.sidecar_path')}</Text>
            <Text size="xs" fw={600}>{status?.sidecar_path || '--'}</Text>
          </Card>
        </SimpleGrid>

        <Alert icon={<IconInfoCircle size={16} />} color="blue" radius="md" mb="sm">
          <Text size="sm">
            {t('project_validation.help')}
          </Text>
        </Alert>

        <Alert icon={<IconInfoCircle size={16} />} color="gray" radius="md">
          <Text size="sm">
            {t('project_validation.scope_hint')}
          </Text>
        </Alert>
      </Paper>

      <Paper withBorder p="md" radius="md">
        <Title order={5} mb="md">{t('project_validation.issue_breakdown')}</Title>
        {entries.length === 0 ? (
          <Text size="sm" c="dimmed">{t('project_validation.no_issues')}</Text>
        ) : (
          <Stack gap="sm">
            {entries.map(([label, count]) => (
              <Group key={label} justify="space-between">
                <Text size="sm">{localizeIssueLabel(label)}</Text>
                <Badge color="orange" variant="light">{count}</Badge>
              </Group>
            ))}
          </Stack>
        )}
      </Paper>
    </Stack>
  );
};

export default ProjectValidation;
