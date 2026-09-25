import React from 'react';
import {
  Accordion, Alert, Anchor, Button, Code, Group, MultiSelect, Paper, ScrollArea, Select, Stack, Text, Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useMarsPipelineDelivery } from '../../hooks/useMarsPipelineDelivery';
import MarsTranslationPackagePanel from './MarsTranslationPackagePanel';
import MarsPublicationIdentity from './MarsPublicationIdentity';

const countOf = (items) => Array.isArray(items) ? items.length : 0;
const entryLabel = (item) => (typeof item === 'string' ? item
  : [item.id, item.reason || item.message || item.code].filter(Boolean).join(': '));

function DeliveryPreview({ plan, busy, execute, t }) {
  const blockers = plan.blockers || [];
  const warnings = plan.warnings || [];
  const uncovered = plan.uncovered_entry_count ?? countOf(blockers);
  const sizeMb = (plan.total_size_bytes || 0) / 1_000_000;
  const issues = blockers.length ? blockers : warnings;
  const publication = plan.publication_binding;
  return (
    <Stack gap="xs">
      <Text size="sm">{t('mars_pipeline.delivery_summary', '{{entries}} translated entries · {{files}} files · {{size}} MB', {
        entries: plan.localized_entry_count ?? 0,
        files: plan.file_count ?? 0,
        size: sizeMb.toFixed(2),
      })}</Text>
      {publication?.status === 'bound' && <Alert color="blue">
        <Stack gap={4}>
          <Text size="sm">{t('mars_pipeline.plan_publication_bound', 'This reviewed export targets Workshop item {{id}}.', {
            id: publication.steam_id,
          })}</Text>
          {publication.url && <Anchor href={publication.url} target="_blank" rel="noreferrer">{publication.url}</Anchor>}
        </Stack>
      </Alert>}
      {publication?.status === 'unbound' && <Alert color="yellow">
        {t('mars_pipeline.plan_publication_unbound', 'This reviewed export has no Workshop item linked.')}
      </Alert>}
      {uncovered > 0 && <Alert color="yellow">
        {t('mars_pipeline.uncovered_summary', '{{count}} entries are not covered by this delivery. Export stays blocked until the scope is reviewed.', {
          count: uncovered,
        })}
      </Alert>}
      {issues.length > 0 && <Accordion variant="contained">
        <Accordion.Item value="issues">
          <Accordion.Control>{t('mars_pipeline.delivery_issue_details', 'Show affected text entries ({{count}})', {
            count: issues.length,
          })}</Accordion.Control>
          <Accordion.Panel>
            <ScrollArea.Autosize mah={220}>
              {issues.map((item, index) => <Text size="sm" key={`${item.id || item}-${index}`} my="xs">
                {entryLabel(item)}
              </Text>)}
            </ScrollArea.Autosize>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>}
      {(plan.installation_steps || []).map((step) => <Text key={step} size="sm">{step}</Text>)}
      <Button loading={busy} disabled={!plan.allowed_actions?.includes('approve_delivery')} onClick={execute}>
        {t('mars_pipeline.export', 'Generate local package')}
      </Button>
    </Stack>
  );
}

export default function MarsPipelineDelivery({ projectId, gameId }) {
  const { t } = useTranslation();
  const flow = useMarsPipelineDelivery(projectId, gameId);
  if (gameId !== 'surviving_mars') return null;
  if (flow.options && !flow.options.supported) {
    return <MarsTranslationPackagePanel projectId={projectId} gameId={gameId} />;
  }
  if (!flow.options && !flow.error) return null;
  return (
    <Paper withBorder p="md" mb="md" data-remis-surface="paper">
      <Stack gap="sm">
        <Title order={3}>{t('mars_pipeline.delivery_title', 'Internationalized Mod delivery')}</Title>
        {flow.mode === 'source_copy' && <MarsPublicationIdentity projectId={projectId} onBindingChanged={flow.publicationChanged} />}
        {flow.error && <Alert color="red" role="alert">{flow.error}</Alert>}
        <Text size="sm">{t('mars_pipeline.run', 'Preparation run')}: <Code>{flow.options?.run_id}</Code></Text>
        <Select label={t('mars_pipeline.mode', 'Delivery mode')} value={flow.mode} disabled={flow.busy}
          onChange={(value) => flow.update('mode', value)} data={[
            { value: 'text_only', label: t('mars_pipeline.text_only', 'Translation text only') },
            { value: 'source_copy', label: t('mars_pipeline.source_copy', 'Complete internationalized copy') },
          ]} />
        <Text size="sm">{flow.mode === 'source_copy'
          ? t('mars_pipeline.source_copy_help', 'Includes every source asset and creates a new Mod ID. Disable the Workshop original and older translation patches before enabling this copy.')
          : t('mars_pipeline.text_only_help', 'Creates an independent localization Mod without copying the original assets or rewriting the original Lua.')}</Text>
        {flow.options?.source_copy_requires_preparation && <Alert color="yellow">
          {t('mars_pipeline.source_copy_requires_preparation', 'To include Lua text, prepare this archive again as a complete copy, then translate the additional entries.')}
        </Alert>}
        <MultiSelect label={t('mars_pipeline.outputs', 'Completed language outputs')} value={flow.selected} disabled={flow.busy}
          onChange={(value) => flow.update('selected', value)}
          data={(flow.options?.translation_outputs || []).map((item) => ({ value: item.output_folder_name, label: item.output_folder_name }))} />
        <Group>
          <Button variant="subtle" disabled={flow.busy} onClick={flow.reload}>{t('button_refresh', 'Refresh')}</Button>
          <Button variant="light" disabled={flow.busy || !flow.selected.length
            || (flow.mode === 'source_copy' && flow.options?.source_copy_requires_preparation)} onClick={flow.preview}>
            {t('mars_pipeline.preview', 'Preview delivery')}
          </Button>
        </Group>
        {flow.plan && <DeliveryPreview plan={flow.plan} busy={flow.busy} execute={flow.execute} t={t} />}
        {flow.result && <Alert color="green">
          <Text>{t('mars_pipeline.generated', 'Package generated. Installation and in-game checks remain manual.')}</Text>
          <Code block>{flow.result.package_path || flow.result.output_path}</Code>
        </Alert>}
        {(flow.result?.warnings || []).map((warning) => <Alert key={warning} color="yellow">{warning}</Alert>)}
      </Stack>
    </Paper>
  );
}
