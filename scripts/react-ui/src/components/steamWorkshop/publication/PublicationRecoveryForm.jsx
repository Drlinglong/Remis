import { useState } from 'react';
import { Button, Checkbox, Select, Stack, Text, TextInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { isPublishedFileId } from './publicationValidation';

export default function PublicationRecoveryForm({ plan, busy, onVerify, onRecovered }) {
  const { t } = useTranslation();
  const [resolution, setResolution] = useState('item_present');
  const [itemId, setItemId] = useState(plan.result?.published_file_id || plan.progress?.published_file_id || '');
  const [verified, setVerified] = useState(false);
  const canVerify = verified && (resolution === 'item_absent' || isPublishedFileId(itemId));
  const submit = async () => {
    const request = { verified: true, resolution, published_file_id: resolution === 'item_present' ? itemId : null };
    if (await onVerify(plan.plan_id, request)) onRecovered(request);
  };
  return (
    <Stack mt="md">
      <Text size="sm">{t('workshop_publication.recovery_intro')}</Text>
      <Select label={t('workshop_publication.recovery_outcome')} value={resolution} allowDeselect={false}
        data={['item_present', 'item_absent'].map((value) => ({ value, label: t(`workshop_publication.resolution.${value}`) }))}
        onChange={(value) => { setResolution(value); setVerified(false); }} disabled={busy} />
      {resolution === 'item_present' && <TextInput label={t('workshop_publication.item_id')} value={itemId}
        onChange={(event) => { setItemId(event.currentTarget.value); setVerified(false); }} disabled={busy} />}
      <Checkbox label={t('workshop_publication.verification_approval')} checked={verified}
        onChange={(event) => setVerified(event.currentTarget.checked)} disabled={busy} />
      <Button variant="default" disabled={!canVerify || busy} onClick={submit}>{t('workshop_publication.record_verification')}</Button>
    </Stack>
  );
}
