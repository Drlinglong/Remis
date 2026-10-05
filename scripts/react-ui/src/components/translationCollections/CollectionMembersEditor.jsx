import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Checkbox, Group, MultiSelect, Select, Stack, Text, TextInput } from '@mantine/core';

export function CollectionMembersEditor({ collection, projects, languages, optionsByProject, optionsLoading, busy, draftDirty, onLoadOptions, onSave, onEdit, t }) {
  const matchingProjects = useMemo(() => projects.filter((project) => project.game_id === collection.game_id), [projects, collection.game_id]);
  const [members, setMembers] = useState(collection.members || []);
  const [title, setTitle] = useState(collection.title || '');
  const [description, setDescription] = useState(collection.description || '');
  const [targetLanguages, setTargetLanguages] = useState(collection.target_languages || []);
  const [projectId, setProjectId] = useState(null);
  useEffect(() => { setMembers(collection.members || []); setTitle(collection.title || ''); setDescription(collection.description || ''); setTargetLanguages(collection.target_languages || []); setProjectId(null); }, [collection]);
  useEffect(() => { (collection.members || []).forEach((member) => { if (!optionsByProject[member.project_id]) onLoadOptions(member.project_id); }); }, [collection, optionsByProject, onLoadOptions]);
  const addProject = (value) => {
    onEdit();
    setProjectId(value);
    if (value && !members.some((member) => member.project_id === value)) {
      setMembers((current) => [...current, { project_id: value, outputs: [] }]);
      onLoadOptions(value);
    }
  };
  const toggleOutput = (memberId, output, checked) => { onEdit(); setMembers((current) => current.map((member) => {
    if (member.project_id !== memberId) return member;
    const key = `${output.language_code}:${output.output_folder_name}`;
    const outputs = member.outputs || [];
    return { ...member, outputs: checked
      ? [...outputs.filter((item) => item.language_code !== output.language_code), { language_code: output.language_code, output_folder_name: output.output_folder_name }]
      : outputs.filter((item) => `${item.language_code}:${item.output_folder_name}` !== key) };
  })); };
  return <Stack>
    <Select label={t('translation_collections.add_project')} data={matchingProjects.map((project) => ({ value: project.project_id, label: project.name }))} value={projectId} onChange={addProject} searchable clearable disabled={busy} />
    {members.map((member) => {
      const selectedKeys = new Set((member.outputs || []).map((output) => `${output.language_code}:${output.output_folder_name}`));
      const project = matchingProjects.find((item) => item.project_id === member.project_id);
      const outputs = optionsByProject[member.project_id]?.translation_outputs || [];
      const warnings = optionsByProject[member.project_id]?.warnings || [];
      return <Stack key={member.project_id} gap="xs">
        <Group justify="space-between"><Text fw={600}>{project?.name || member.project_id}</Text><Button size="compact-sm" variant="subtle" color="red" disabled={busy} onClick={() => { onEdit(); setMembers((current) => current.filter((item) => item.project_id !== member.project_id)); }}>{t('translation_collections.remove_member')}</Button></Group>
        <Button size="xs" variant="light" onClick={() => onLoadOptions(member.project_id, true)} loading={Boolean(optionsLoading[member.project_id])} disabled={busy}>{t('translation_collections.refresh_outputs')}</Button>
        {warnings.map((warning, index) => <Alert key={index} color="yellow">{typeof warning === 'string' ? warning : warning.message}</Alert>)}
        {outputs.filter((output) => targetLanguages.includes(output.language_code)).map((output) => {
          const key = `${output.language_code}:${output.output_folder_name}`;
          return <Checkbox key={key} label={`${output.language_code} · ${output.output_folder_name}`} checked={selectedKeys.has(key)} disabled={busy || Boolean(optionsLoading[member.project_id])} onChange={(event) => toggleOutput(member.project_id, output, event.currentTarget.checked)} />;
        })}
      </Stack>;
    })}
    <TextInput label={t('translation_collections.title')} value={title} disabled={busy} onChange={(event) => { onEdit(); setTitle(event.currentTarget.value); }} />
    <TextInput label={t('translation_collections.description')} value={description} disabled={busy} onChange={(event) => { onEdit(); setDescription(event.currentTarget.value); }} />
    <MultiSelect label={t('translation_collections.languages')} data={languages} value={targetLanguages} disabled={busy} onChange={(value) => { onEdit(); setTargetLanguages(value); setMembers((current) => current.map((member) => ({ ...member, outputs: (member.outputs || []).filter((output) => value.includes(output.language_code)) }))); }} />
    {draftDirty && <Text size="sm" c="orange">{t('translation_collections.unsaved_changes')}</Text>}
    <Button loading={busy} disabled={busy} onClick={() => onSave({ title, description, target_languages: targetLanguages, members })}>{t('translation_collections.save_members')}</Button>
  </Stack>;
}
