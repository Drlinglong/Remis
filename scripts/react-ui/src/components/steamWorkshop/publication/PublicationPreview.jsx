import { Alert, Anchor, Badge, Code, Group, Image, Paper, ScrollArea, Stack, Table, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { BbcodePreview } from '../description/BbcodePreview';

export function PublicationOutcome({ plan }) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs">
      <Group>
        <Badge color={plan.status === 'succeeded' ? 'green' : plan.status === 'preview' ? 'gray' : 'orange'}>
          {t(`workshop_publication.status.${plan.status}`)}
        </Badge>
        <Text size="sm">{plan.target.title}</Text>
      </Group>
      {plan.result?.code && <Text size="sm">{t(`workshop_publication.code.${plan.result.code}`, { defaultValue: plan.result.code })}</Text>}
      {plan.progress?.bytes_total > 0 && <Text size="sm">{plan.progress.bytes_done} / {plan.progress.bytes_total} bytes</Text>}
      {plan.result?.workshop_url && (
        <Anchor href={plan.result.workshop_url} target="_blank" rel="noopener noreferrer">{t('workshop_publication.open_item')}</Anchor>
      )}
      {['unknown', 'legal_agreement_required'].includes(plan.status) && <Alert color="orange">{t('workshop_publication.verify_remote')}</Alert>}
      {plan.status === 'resolved' && <Text size="sm">{t('workshop_publication.manual_verification_recorded')}</Text>}
    </Stack>
  );
}

export default function PublicationPreview({ plan }) {
  const { t } = useTranslation();
  return (
    <Paper withBorder p="md" data-remis-surface="paper">
      <Stack>
        <PublicationOutcome plan={plan} />
        <Text fw={600}>{t('workshop_publication.target_summary', {
          app: plan.target.app_id, item: plan.target.published_file_id || t('workshop_publication.new_item'),
          visibility: t(`workshop_publication.visibility.${plan.target.visibility}`),
        })}</Text>
        <Text size="sm">{plan.content_path}</Text>
        <Text size="sm">{t('workshop_publication.file_summary', { count: plan.file_count, bytes: plan.total_bytes })}</Text>
        <Text size="sm">{t('workshop_publication.validation_scope', { count: plan.validation.entry_count })}</Text>
        <Text size="sm">{t('workshop_publication.account', { id: plan.runtime.steam_id || '—' })}</Text>
        {!plan.runtime.ready && <Alert color="orange">{t(`workshop_publication.code.${plan.runtime.code}`, { defaultValue: plan.runtime.code })}</Alert>}
        <Code block>{plan.fingerprint}</Code>
        <Image w={128} src={`/api/steam-workshop/versions/${encodeURIComponent(plan.cover_version_id)}/content`} alt={t('steam_workshop.cover_label')} />
        <BbcodePreview bbcode={plan.description} />
        <Text size="sm">{plan.target.change_note}</Text>
        <Text size="sm">{t('workshop_publication.mode_label')}: {t(`workshop_publication.mode.${plan.target.mode}`)}</Text>
        <Text size="sm">{t('workshop_publication.language')}: {plan.target.language}</Text>
        <Text size="sm">{t('workshop_publication.tags')}: {plan.target.tags.join(', ') || '—'}</Text>
        <ScrollArea h={160}>
          <Table>
            <Table.Thead><Table.Tr><Table.Th>{t('workshop_publication.file')}</Table.Th><Table.Th>SHA-256</Table.Th></Table.Tr></Table.Thead>
            <Table.Tbody>{plan.files.map((file) => <Table.Tr key={file.path}><Table.Td>{file.path}</Table.Td><Table.Td><Code>{file.sha256}</Code></Table.Td></Table.Tr>)}</Table.Tbody>
          </Table>
        </ScrollArea>
      </Stack>
    </Paper>
  );
}
