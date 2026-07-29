import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Badge, Button, Card, Group, Loader, Paper, ScrollArea, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconEdit, IconInfoCircle, IconRefresh, IconRobot } from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import api from '../../utils/api';
import { useTranslation } from 'react-i18next';
import { buildProofreadingUrl } from '../../utils/proofreadingLinks';
import styles from '../../pages/ProjectManagement.module.css';

const ProjectValidation = ({ projectId }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedSidecarPath, setSelectedSidecarPath] = useState(null);

  const localizeIssueLabel = useCallback((code) => {
    if (!code) return t('agent_workshop.unknown_issue');
    const key = String(code).trim();
    const known = {
      validation_vic3_variable_parity_mismatch: t('agent_workshop.issue_vic3_variable_parity'),
      validation_vic3_color_tags_mismatch: t('agent_workshop.issue_vic3_color_tags'),
      validation_format_marker_parity_mismatch: t('agent_workshop.issue_format_marker_parity'),
      validation_residual_punctuation_found: t('agent_workshop.validation_residual_punctuation_found'),
      validation_invalid_key_format: t('agent_workshop.issue_invalid_key_format'),
      'Invalid key format': t('agent_workshop.issue_invalid_key_format'),
    };
    if (known[key]) return known[key];

    // Defensive fallback translation for legacy cached or hardcoded Chinese labels
    if (key.includes('颜色标签') && key.includes('结束符')) {
      return t('agent_workshop.issue_vic3_color_tags');
    }
    if (key.includes('格式标记') || key.includes('format marker') || key.includes('format_marker_parity')) {
      return t('agent_workshop.issue_format_marker_parity');
    }
    if (key.includes('源语言标点') || key.includes('标点符号')) {
      return t('agent_workshop.validation_residual_punctuation_found');
    }
    if (key.includes('变量数量') || key.includes('变量')) {
      return t('agent_workshop.issue_vic3_variable_parity');
    }

    if (key.startsWith('validation_')) {
      return t('agent_workshop.issue_validation_generic');
    }
    return key;
  }, [t]);

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      const params = selectedSidecarPath ? `?sidecar_path=${encodeURIComponent(selectedSidecarPath)}` : '';
      const res = await api.get(`/api/project/${projectId}/validation-status${params}`);
      const payload = res.data || null;
      setStatus(payload);
      if (!selectedSidecarPath && payload?.sidecar_path) {
        setSelectedSidecarPath(payload.sidecar_path);
      }
    } catch (error) {
      console.error('Failed to load validation status', error);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedSidecarPath]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const refreshSidecar = async () => {
    try {
      setRefreshing(true);
      const params = new URLSearchParams({ project_id: projectId, force: 'true' });
      const activeSidecarPath = selectedSidecarPath || status?.sidecar_path;
      if (activeSidecarPath) params.set('sidecar_path', activeSidecarPath);
      await api.get(`/api/agent-workshop/scan?${params.toString()}`);
      await loadStatus();
    } catch (error) {
      console.error('Failed to refresh workshop sidecar', error);
    } finally {
      setRefreshing(false);
    }
  };

  const openWorkshop = () => {
    navigate('/agent-workshop', { state: { projectId, sidecarPath: selectedSidecarPath || status?.sidecar_path || null } });
  };

  const entries = useMemo(
    () => Object.entries(status?.issue_type_counts || {}).sort((a, b) => b[1] - a[1]),
    [status]
  );

  const sidecarOptions = useMemo(
    () => (status?.sidecar_candidates || []).map((candidate) => ({
      value: candidate.path,
      label: `${candidate.path} (${candidate.issue_count ?? 0})`,
    })),
    [status]
  );
  const issues = status?.issues || [];

  if (loading) {
    return (
      <Paper data-remis-surface="paper" withBorder p="lg" radius="md" className={styles.paperPanel}>
        <Group justify="center">
          <Loader size="sm" />
        </Group>
      </Paper>
    );
  }

  return (
    <Stack id="project-validation-panel" p="md" gap="lg">
      <Paper data-remis-surface="paper" withBorder p="md" radius="md" className={styles.paperPanel}>
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
            <Button id="project-validation-open-workshop-btn" leftSection={<IconRobot size={16} />} onClick={openWorkshop}>
              {t('project_validation.open_workshop')}
            </Button>
          </Group>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} mb="md">
          <Card data-remis-surface="paper" withBorder p="sm" radius="md" className={styles.paperInset}>
            <Text size="xs" c="dimmed">{t('project_validation.issues_count')}</Text>
            <Text size="lg" fw={700}>{status?.issues_count ?? 0}</Text>
          </Card>
          <Card data-remis-surface="paper" withBorder p="sm" radius="md" className={styles.paperInset}>
            <Text size="xs" c="dimmed">{t('project_validation.last_updated')}</Text>
            <Text size="sm" fw={600}>{status?.last_updated_at ? new Date(status.last_updated_at).toLocaleString() : '--'}</Text>
          </Card>
          <Card data-remis-surface="paper" withBorder p="sm" radius="md" className={styles.paperInset}>
            <Text size="xs" c="dimmed">{t('project_validation.report_count')}</Text>
            <Text size="lg" fw={700}>{status?.report_count ?? 0}</Text>
          </Card>
        </SimpleGrid>

        <Card data-remis-surface="paper" withBorder p="sm" radius="md" mb="md" className={styles.paperInset}>
          {sidecarOptions.length > 0 ? (
            <Select
              label={t('project_validation.sidecar_path')}
              data={sidecarOptions}
              value={selectedSidecarPath || status?.sidecar_path || null}
              onChange={setSelectedSidecarPath}
              searchable
              allowDeselect={false}
              styles={{
                input: {
                  fontWeight: 600,
                },
              }}
            />
          ) : (
            <>
              <Text size="xs" c="dimmed">{t('project_validation.sidecar_path')}</Text>
              <Text
                size="sm"
                fw={600}
                style={{
                  wordBreak: 'break-all',
                  overflowWrap: 'anywhere',
                  whiteSpace: 'normal',
                }}
              >
                {status?.sidecar_path || '--'}
              </Text>
            </>
          )}
        </Card>

        <Alert data-remis-surface="paper" icon={<IconInfoCircle size={16} />} color="blue" radius="md" mb="sm" className={styles.paperAlert}>
          <Text size="sm">
            {t('project_validation.help')}
          </Text>
        </Alert>

        <Alert data-remis-surface="paper" id="project-validation-scope-alert" icon={<IconInfoCircle size={16} />} color="gray" radius="md" className={styles.paperAlert}>
          <Text size="sm">
            {t('project_validation.scope_hint')}
          </Text>
        </Alert>
      </Paper>

      <Paper data-remis-surface="paper" withBorder p="md" radius="md" className={styles.paperPanel}>
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

      {issues.length > 0 && (
        <Paper data-remis-surface="paper" withBorder p="md" radius="md" className={styles.paperPanel}>
          <Title order={5} mb="md">
            {t('proofreading.issue_details', { defaultValue: 'Issue details' })}
          </Title>
          <ScrollArea.Autosize mah={360}>
            <Stack gap="xs">
              {issues.map((issue, index) => (
                <Card data-remis-surface="paper" key={`${issue.file_name}:${issue.key}:${index}`} withBorder p="sm" radius="md" className={styles.paperInset}>
                  <Group justify="space-between" align="flex-start" wrap="nowrap">
                    <Stack gap={3} style={{ minWidth: 0 }}>
                      <Text size="xs" c="dimmed" truncate>{issue.file_name || issue.file_path}</Text>
                      <Text size="sm" fw={700} ff="monospace">{issue.key}</Text>
                      <Text size="xs">{localizeIssueLabel(issue.error_code || issue.error_type)}</Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconEdit size={14} />}
                      disabled={!issue.file_id || !issue.key}
                      onClick={() => navigate(buildProofreadingUrl({
                        projectId,
                        fileId: issue.file_id,
                        entryKey: issue.key,
                        lineHint: issue.line_number,
                      }))}
                    >
                      {t('proofreading.open_entry', { defaultValue: 'Manual proofreading' })}
                    </Button>
                  </Group>
                </Card>
              ))}
            </Stack>
          </ScrollArea.Autosize>
        </Paper>
      )}
    </Stack>
  );
};

export default ProjectValidation;
