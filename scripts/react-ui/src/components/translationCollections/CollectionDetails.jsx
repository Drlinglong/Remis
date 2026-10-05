import React, { useEffect, useState } from 'react';
import { Button, Checkbox, Code, Divider, Group, Stack, Text, TextInput } from '@mantine/core';
import { CollectionMembersEditor } from './CollectionMembersEditor';
import { CollectionPreviewReview } from './CollectionPreviewReview';

export function CollectionDetails({ collection, projects, languages, apiState, t }) {
  const [steamId, setSteamId] = useState(collection.steam_id || '');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [approved, setApproved] = useState(false);
  const [conflictsAcknowledged, setConflictsAcknowledged] = useState(false);
  const [steamDirty, setSteamDirty] = useState(false);
  useEffect(() => { setSteamId(collection.steam_id || ''); setConfirmDelete(false); setApproved(false); setSteamDirty(false); }, [collection]);
  useEffect(() => { setApproved(false); setConflictsAcknowledged(false); }, [apiState.preview?.plan_id]);
  const { busy, projectOptions, optionsLoading, preview, history, draftDirty, loadProjectOptions, save, bindPublication, plan, exportPackage, remove } = apiState;
  const isMars = /mars/i.test(collection.game_id);
  return <Stack mt="md">
    <Text size="sm">{isMars ? t('translation_collections.mars_mode') : t('translation_collections.bundle_mode')}</Text>
    <CollectionMembersEditor collection={collection} projects={projects} languages={languages} optionsByProject={projectOptions} optionsLoading={optionsLoading} busy={busy} draftDirty={draftDirty} onLoadOptions={loadProjectOptions} onSave={save} onEdit={apiState.markDraftDirty} t={t} />
    <Divider />
    <Text fw={600}>{t('translation_collections.publication')}</Text>
    <Group align="end"><TextInput label={t('translation_collections.steam_id')} value={steamId} disabled={busy} onChange={(event) => { apiState.invalidatePreview(); setSteamDirty(true); setSteamId(event.currentTarget.value); }} /><Button loading={busy} disabled={busy || draftDirty || !steamDirty} onClick={async () => { const result = await bindPublication(steamId.trim()); if (result) setSteamDirty(false); }}>{steamId.trim() ? t('translation_collections.bind_publication') : t('translation_collections.remove_publication')}</Button></Group>
    {collection.steam_id && <Text size="sm">{t('translation_collections.bound_id')}: <Code>{collection.steam_id}</Code></Text>}
    <Divider />
    <Group><Button variant="light" loading={busy} disabled={busy || draftDirty || steamDirty} onClick={plan}>{t('translation_collections.preview')}</Button>
      <Checkbox label={t('translation_collections.approve_export')} checked={approved} disabled={busy || draftDirty || steamDirty} onChange={(event) => setApproved(event.currentTarget.checked)} />
      {Boolean(preview?.inspection?.conflicts?.length) && <Checkbox label={t('translation_collections.acknowledge_conflicts')} checked={conflictsAcknowledged} disabled={busy} onChange={(event) => setConflictsAcknowledged(event.currentTarget.checked)} />}
      <Button color="teal" loading={busy} disabled={busy || draftDirty || steamDirty || !preview?.inspection?.can_export || !approved || (Boolean(preview?.inspection?.conflicts?.length) && !conflictsAcknowledged)} onClick={exportPackage}>{t('translation_collections.export')}</Button>
    </Group>
    {preview && <div aria-live="polite"><CollectionPreviewReview inspection={preview.inspection || {}} projects={projects} t={t} /></div>}
    <Divider />
    <Text fw={600}>{t('translation_collections.history')}</Text>
    {history.length ? history.map((item, index) => <Text size="sm" key={item.export_id || item.package_path || index}>{item.exported_at || item.created_at || ''} · {item.file_count ?? ''} · {item.package_path || ''}</Text>) : <Text size="sm" c="dimmed">{t('translation_collections.no_history')}</Text>}
    <Checkbox color="red" label={t('translation_collections.confirm_delete')} checked={confirmDelete} onChange={(event) => setConfirmDelete(event.currentTarget.checked)} />
    <Button color="red" variant="light" disabled={!confirmDelete || busy} onClick={remove}>{t('translation_collections.delete')}</Button>
  </Stack>;
}
