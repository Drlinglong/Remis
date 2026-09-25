import React from 'react';
import { Alert, Anchor, Button, Group, Stack, TextInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useMarsPublicationIdentity } from '../../hooks/useMarsPublicationIdentity';

export default function MarsPublicationIdentity({ projectId, onBindingChanged }) {
  const { t } = useTranslation();
  const identity = useMarsPublicationIdentity(projectId);
  const validId = /^\d+$/.test(identity.steamId.trim()) && BigInt(identity.steamId.trim() || '0') > 0n;
  const bound = identity.identity?.status === 'bound';
  const unbound = identity.identity?.status === 'unbound';

  const save = async () => {
    const saved = await identity.bind();
    if (saved) onBindingChanged?.();
  };

  if (identity.loading) return null;
  return (
    <Stack gap="xs">
      {identity.error && <Alert color="red" role="alert">{identity.error}</Alert>}
      {bound ? (
        <Alert color="blue">
          <Stack gap={4}>
            <span>{t('mars_pipeline.publication_bound', 'Subsequent full-copy exports will target this Workshop item:')}</span>
            <Anchor href={identity.identity.url} target="_blank" rel="noreferrer">
              {identity.identity.url || identity.identity.steam_id}
            </Anchor>
            <span>{t('mars_pipeline.publication_old_exports', 'Previously exported folders are unchanged.')}</span>
            <span>{t('mars_pipeline.publication_locked', 'This Workshop link is locked in Remis.')}</span>
          </Stack>
        </Alert>
      ) : unbound ? (
        <Alert color="yellow">
          {t('mars_pipeline.publication_unbound', 'No Workshop item is linked. Publishing this project from the Game Editor will create a new Workshop item.')}
        </Alert>
      ) : (
        <Alert color="gray">
          {t('mars_pipeline.publication_unavailable', 'Workshop identity is unavailable. Refresh project data before binding an item.')}
        </Alert>
      )}
      <Group align="end" wrap="wrap">
        <TextInput label={t('mars_pipeline.publication_id', 'Your Workshop item ID')}
          description={t('mars_pipeline.publication_local_only', 'Saved locally for this project. This does not upload or change anything on Steam.')}
          value={identity.steamId} inputMode="numeric" disabled={identity.saving || identity.loading || bound}
          onChange={(event) => identity.updateSteamId(event.currentTarget.value)} />
        {!bound && <Button variant="light" disabled={!identity.identity || identity.error || !validId || identity.saving || identity.loading}
          loading={identity.saving} onClick={save}>
          {t('mars_pipeline.publication_bind', 'Save Workshop item link')}
        </Button>}
      </Group>
    </Stack>
  );
}
