import React from 'react';
import { Select, Stack, Table, Text } from '@mantine/core';

export default function MarsSourceSelection({ flow, languageOptions, t }) {
  const tables = flow.inspection?.source_tables || [];
  const blockers = flow.plan?.source_blockers?.length
    ? flow.plan.source_blockers : flow.inspection?.source_blockers || [];
  const selectedTable = tables.find((table) => table.path === flow.sourceTable);
  const samples = selectedTable?.samples || [];
  return (
    <Stack gap="sm">
      <Select label={t('mars_pipeline.source_language', 'Source language')}
        data={languageOptions} value={flow.sourceLanguage || null} disabled={flow.busy}
        onChange={(value) => value && flow.update('sourceLanguage', value)} searchable />
      <Select label={t('mars_pipeline.source_table', 'Source CSV table (optional)')}
        description={t('mars_pipeline.source_table_help', 'Inspect first to discover localization tables.')}
        data={tables.map((table) => ({ value: table.path, label: `${table.path} (${table.row_count})` }))}
        value={flow.sourceTable || null} disabled={flow.busy || tables.length === 0} clearable
        onChange={(value) => flow.update('sourceTable', value || '')} searchable />
      <Select label={t('mars_pipeline.source_column', 'Source text column')}
        data={[
          { value: 'Text', label: t('mars_pipeline.source_text', 'Text') },
          { value: 'Translation', label: t('mars_pipeline.source_translation', 'Translation') },
        ]}
        value={flow.sourceColumn} disabled={flow.busy}
        onChange={(value) => value && flow.update('sourceColumn', value)} />
      {samples.length > 0 && <Stack gap={4}>
        <Text size="sm" fw={600}>{t('mars_pipeline.source_samples', 'Source samples')}</Text>
        <Table.ScrollContainer minWidth={420} mah={180}>
          <Table striped withTableBorder>
            <Table.Thead><Table.Tr>
              <Table.Th>{t('mars_pipeline.source_id', 'ID')}</Table.Th>
              <Table.Th>{t('mars_pipeline.source_text', 'Text')}</Table.Th>
              <Table.Th>{t('mars_pipeline.source_translation', 'Translation')}</Table.Th>
            </Table.Tr></Table.Thead>
            <Table.Tbody>{samples.map((sample) => <Table.Tr key={sample.id}>
              <Table.Td>{sample.id}</Table.Td><Table.Td>{sample.text}</Table.Td>
              <Table.Td>{sample.translation}</Table.Td>
            </Table.Tr>)}</Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Stack>}
      {blockers.map((blocker, index) => (
        <Text key={blocker.id || `${blocker.code}-${index}`} size="sm" c="red" role="alert">
          {blocker.message}
        </Text>
      ))}
    </Stack>
  );
}
