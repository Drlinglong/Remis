import React from 'react';
import { Badge, Card, Code, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

const percent = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
const count = (value) => Number(value || 0).toLocaleString();

function Metric({ label, value }) {
  return (
    <Paper withBorder p="sm" radius="sm" data-remis-surface="paper">
      <Text size="xs" c="dimmed">{label}</Text>
      <Text fw={700}>{value}</Text>
    </Paper>
  );
}

function DetailSection({ title, children, open = false }) {
  return (
    <details open={open}>
      <summary><Text component="span" fw={700}>{title}</Text></summary>
      <Stack gap="xs" mt="xs">{children}</Stack>
    </details>
  );
}

export default function ContextAnalysisReportPanel({ report }) {
  const { t } = useTranslation();
  if (!report) return null;

  const input = report.input_and_chunking || {};
  const integrity = report.source_integrity?.totals || {};
  const assignments = report.unit_assignment_integrity || {};
  const coverage = report.coverage_and_contamination || {};
  const execution = report.model_execution || {};
  const chains = report.final_chain_resolution || [];
  const unassigned = report.unassigned_units || [];
  const boundary = report.chunk_boundary_impact || {};
  const repairs = assignments.repair_reasons || [];
  const supporting = chains.reduce((total, chain) => total + Number(chain.supporting_context || 0), 0);
  const gatePassed = Boolean(integrity.gate_passed)
    && (assignments.missing || []).length === 0
    && (assignments.duplicate || []).length === 0
    && (assignments.unexpected || []).length === 0;

  return (
    <Card withBorder radius="md" p="lg" data-remis-surface="surface" data-testid="context-analysis-report">
      <Group justify="space-between" align="flex-start" mb="md">
        <div>
          <Title order={3}>{t('context_report.title')}</Title>
          <Text size="sm" c="dimmed">{t('context_report.subtitle')}</Text>
        </div>
        <Badge color={gatePassed ? 'teal' : 'red'} variant="light">
          {t(gatePassed ? 'context_report.gates_passed' : 'context_report.gates_failed')}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} spacing="sm" mb="md">
        <Metric label={t('context_report.raw_keys')} value={count(integrity.raw)} />
        <Metric label={t('context_report.source_items')} value={count(input.source_items)} />
        <Metric label={t('context_report.local_units')} value={count(input.local_units)} />
        <Metric label={t('context_report.chunks')} value={count(input.chunks)} />
        <Metric label={t('context_report.delivery_coverage')} value={percent(coverage.delivery_coverage)} />
        <Metric label={t('context_report.supporting_context')} value={count(supporting)} />
      </SimpleGrid>

      <Stack gap="sm">
        <DetailSection title={t('context_report.assignment_integrity')} open>
          <Group gap="xs" wrap="wrap">
            {['missing', 'duplicate', 'unexpected', 'unassigned', 'multi_linked'].map((key) => (
              <Badge key={key} color={Number(assignments[key]?.length ?? assignments[key] ?? 0) ? 'orange' : 'teal'} variant="outline">
                {t(`context_report.${key}`)}: {count(assignments[key]?.length ?? assignments[key])}
              </Badge>
            ))}
          </Group>
        </DetailSection>

        <DetailSection title={t('context_report.model_execution')}>
          <Text size="sm">{t('context_report.calls')}: {count(execution.call_count)}</Text>
          <Text size="sm">{t('context_report.reasoning')}: {execution.reasoning_profile || t('task_detail.not_available')}</Text>
          <Text size="sm">{t('context_report.tokens')}: {execution.token_usage ? count(execution.token_usage.total_tokens) : t('task_detail.not_available')}</Text>
          <Text size="sm">{t('context_report.cost')}: {execution.cost ? `$${Number(execution.cost.amount).toFixed(6)} USD${execution.cost.complete ? '' : ' *'}` : t('task_detail.not_available')}</Text>
          <Text size="xs" c="dimmed">{execution.usage_note}</Text>
        </DetailSection>

        <DetailSection title={`${t('context_report.repairs')} (${repairs.length})`}>
          {repairs.length === 0 && <Text size="sm" c="dimmed">{t('context_report.no_repairs')}</Text>}
          {repairs.map((repair, index) => (
            <Paper key={`${repair.stage}-${repair.batch_index ?? index}`} withBorder p="sm" data-remis-surface="paper">
              <Text size="sm" fw={700}>{repair.stage} · {repair.reason || 'unknown'}</Text>
              {repair.detail && <Code block mt="xs">{repair.detail}</Code>}
            </Paper>
          ))}
        </DetailSection>

        <DetailSection title={`${t('context_report.final_chains')} (${chains.length})`}>
          {chains.map((chain) => (
            <Paper key={chain.chain_id} withBorder p="sm" data-remis-surface="paper">
              <Text fw={700}>{chain.chain_id}</Text>
              <Group gap="xs" mt={6} wrap="wrap">
                <Badge variant="light">primary {count(chain.primary_members)}</Badge>
                <Badge variant="light" color="blue">supporting {count(chain.supporting_context)}</Badge>
                <Badge variant="light" color="gray">theme {count(chain.theme_related)}</Badge>
                <Badge variant="outline">evidence {count(chain.evidence)}</Badge>
              </Group>
            </Paper>
          ))}
        </DetailSection>

        <DetailSection title={t('context_report.boundary_impact')}>
          <Text size="sm">{t('context_report.cross_chunk_merges')}: {count(boundary.cross_chunk_merged_chains?.length)}</Text>
          <Text size="sm">{t('context_report.membership_added')}: {count(boundary.membership_added)}</Text>
          <Text size="sm">{t('context_report.membership_removed')}: {count(boundary.membership_removed)}</Text>
          <Text size="sm">{t('context_report.boundary_unassigned')}: {count(boundary.boundary_unassigned_units?.length)}</Text>
        </DetailSection>

        <DetailSection title={`${t('context_report.unassigned_units')} (${unassigned.length})`}>
          {unassigned.map((unit) => (
            <Paper key={unit.unit_id} withBorder p="sm" data-remis-surface="paper">
              <Group justify="space-between" wrap="nowrap">
                <Code>{unit.unit_id}</Code>
                <Badge variant="outline">chunk {unit.chunk ?? '--'}</Badge>
              </Group>
              <Text size="sm" mt={6} style={{ overflowWrap: 'anywhere' }}>
                {(unit.localization_keys || []).join(', ')}
              </Text>
            </Paper>
          ))}
        </DetailSection>
      </Stack>
    </Card>
  );
}
