import React, { useState } from 'react';
import { Alert, Button, Group, Modal, ScrollArea, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useTranslationCollections } from '../../hooks/useTranslationCollections';
import { CollectionCreateForm } from './CollectionCreateForm';
import { CollectionDetails } from './CollectionDetails';

export function TranslationCollectionsModal({ opened, onClose, projects, games, languages }) {
  const { t } = useTranslation();
  const state = useTranslationCollections(opened);
  const [creating, setCreating] = useState(false);
  const collectionGames = games.map((game) => ({ value: game.value, label: game.label, supported_language_codes: game.supported_language_codes }));
  const languageOptions = languages.map((language) => ({ value: language.value, label: language.label }));
  const activeProjects = projects.filter((project) => project.status === 'active');
  const selectedGame = games.find((game) => game.value === state.selected?.game_id);
  const selectedLanguages = selectedGame?.supported_language_codes?.length
    ? languageOptions.filter((language) => selectedGame.supported_language_codes.includes(language.value))
    : languageOptions;
  return <Modal opened={opened} onClose={() => { state.close(); setCreating(false); onClose(); }} size="xl" title={t('translation_collections.title_panel')}>
    <Stack>
      {state.error && <Alert color="red" title={t('translation_collections.error_title')}>{state.error}</Alert>}
      {state.selected ? <>
        <Group justify="space-between"><Button variant="subtle" disabled={state.busy} onClick={() => { state.clearSelection(); setCreating(false); }}>{t('translation_collections.back')}</Button><Text fw={700}>{state.selected.title}</Text></Group>
        <Text size="sm" c="dimmed">{state.selected.game_id} · {state.selected.target_languages?.join(', ')}</Text>
        <CollectionDetails collection={state.selected} projects={activeProjects} languages={selectedLanguages} apiState={state} t={t} />
      </> : creating ? <>
        <Button variant="subtle" disabled={state.busy} onClick={() => setCreating(false)}>{t('translation_collections.back')}</Button>
        <CollectionCreateForm games={collectionGames} languages={languageOptions} busy={state.busy} onCreate={state.create} t={t} />
      </> : <>
        <Group justify="space-between"><Text>{t('translation_collections.independent_help')}</Text><Button disabled={state.busy} onClick={() => setCreating(true)}>{t('translation_collections.new')}</Button></Group>
        {state.loading && <Text>{t('translation_collections.loading')}</Text>}
        <ScrollArea.Autosize mah={420}>
          {state.collections.map((collection) => <Button key={collection.collection_id} variant="default" fullWidth justify="flex-start" mb="xs" disabled={state.busy} onClick={() => state.openCollection(collection.collection_id)}>{collection.title} · {collection.game_id} · {collection.target_languages?.join(', ')}</Button>)}
          {!state.loading && state.collections.length === 0 && <Text c="dimmed">{t('translation_collections.empty')}</Text>}
        </ScrollArea.Autosize>
      </>}
    </Stack>
  </Modal>;
}
