import React, { useState } from 'react';
import { Button, MultiSelect, Select, Stack, TextInput, Textarea } from '@mantine/core';

export function CollectionCreateForm({ games, languages, busy, onCreate, t }) {
  const [title, setTitle] = useState('');
  const [gameId, setGameId] = useState(null);
  const [targetLanguages, setTargetLanguages] = useState([]);
  const [description, setDescription] = useState('');
  const submit = async (event) => {
    event.preventDefault();
    if (!title.trim() || !gameId || !targetLanguages.length) return;
    const result = await onCreate({ title: title.trim(), game_id: gameId, target_languages: targetLanguages, description, members: [] });
    if (result) { setTitle(''); setDescription(''); }
  };
  return <form onSubmit={submit}>
    <Stack>
      <TextInput label={t('translation_collections.title')} value={title} disabled={busy} onChange={(event) => setTitle(event.currentTarget.value)} required />
      <Select label={t('translation_collections.game')} data={games} value={gameId} onChange={(value) => { setGameId(value); const supported = games.find((game) => game.value === value)?.supported_language_codes; if (supported?.length) setTargetLanguages((current) => current.filter((language) => supported.includes(language))); }} searchable required disabled={busy} />
      <MultiSelect
        label={t('translation_collections.languages')}
        data={languages.filter((language) => !gameId || !games.find((game) => game.value === gameId)?.supported_language_codes?.length || games.find((game) => game.value === gameId).supported_language_codes.includes(language.value))}
        value={targetLanguages}
        onChange={setTargetLanguages}
        searchable
        required
        disabled={busy || !gameId}
      />
      <Textarea label={t('translation_collections.description')} value={description} disabled={busy} onChange={(event) => setDescription(event.currentTarget.value)} />
      <Button type="submit" loading={busy} disabled={busy || !title.trim() || !gameId || !targetLanguages.length}>{t('translation_collections.create')}</Button>
    </Stack>
  </form>;
}
