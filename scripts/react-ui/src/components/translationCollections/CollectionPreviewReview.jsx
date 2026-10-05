import React from 'react';
import { Alert, Code, Stack, Text } from '@mantine/core';

const displayProject = (id, projects) => projects.find((project) => project.project_id === id)?.name || id;

function MemberPreview({ member, projects, t }) {
  const files = (member.outputs || []).flatMap((output) => output.files || []);
  return <details>
    <summary>{displayProject(member.project_id, projects)} · {member.project_id}</summary>
    <Stack gap={4} mt="xs" ml="md">
      {(member.outputs || []).map((output) => <div key={`${member.project_id}-${output.language_code}`}>
        <Text size="sm">{output.language_code} · {output.output_folder_name || t('translation_collections.selected_output')}</Text>
        {output.files?.length ? <ul>{output.files.map((file) => <li key={file.path}><Code>{file.path}</Code></li>)}</ul> : null}
      </div>)}
      {files.length > 0 && <Text size="xs" c="dimmed">{t('translation_collections.member_files', { count: files.length })}</Text>}
    </Stack>
  </details>;
}

function ChangeList({ title, memberIds, projects }) {
  if (!memberIds?.length) return null;
  return <Text size="sm">{title}: {memberIds.map((member) => {
    const id = typeof member === 'string' ? member : member.project_id || member.member_id || String(member);
    return `${displayProject(id, projects)} (${id})`;
  }).join(', ')}</Text>;
}

export function CollectionPreviewReview({ inspection, projects, t }) {
  const members = inspection.members || [];
  const changes = inspection.changes || {};
  const conflicts = inspection.conflicts || [];
  return <Stack gap="xs">
    <Alert color={inspection.can_export ? 'green' : 'yellow'} title={t('translation_collections.preview_result')}>
      <Text size="sm">{t(inspection.mode === 'mars_text_mod' ? 'translation_collections.mars_mode' : 'translation_collections.bundle_mode')}</Text>
      {t('translation_collections.file_count', { count: inspection.file_count || 0 })} · {t('translation_collections.entry_count', { count: inspection.entry_count || 0 })}
      {inspection.runtime_verified === false && <Text size="sm">{t('translation_collections.runtime_unverified')}</Text>}
    </Alert>
    {changes.previous_package_path && <Text size="sm">{t('translation_collections.previous_export')}: <Code>{changes.previous_package_path}</Code></Text>}
    <ChangeList title={t('translation_collections.added_members')} memberIds={changes.added} projects={projects} />
    <ChangeList title={t('translation_collections.removed_members')} memberIds={changes.removed} projects={projects} />
    <ChangeList title={t('translation_collections.selection_changed')} memberIds={changes.selection_changed} projects={projects} />
    <ChangeList title={t('translation_collections.content_changed')} memberIds={changes.content_changed} projects={projects} />
    <Text fw={600}>{t('translation_collections.selected_members')}</Text>
    {members.map((member) => <MemberPreview key={member.project_id} member={member} projects={projects} t={t} />)}
    {conflicts.length > 0 && <Alert color="red" title={t('translation_collections.paradox_conflicts_title')}>
      <Text size="sm" fw={600}>{t('translation_collections.paradox_conflicts_instruction')}</Text>
      <Stack gap="xs" mt="xs">{conflicts.map((conflict, index) => <Text size="sm" key={`${conflict.language_code}-${conflict.key}-${index}`}>
        {conflict.language_code} · <Code>{conflict.key}</Code> · {conflict.projects.map((id) => `${displayProject(id, projects)} (${id})`).join(' ↔ ')}
        {conflict.source_conflict ? ` · ${t('translation_collections.source_conflict')}` : ''}{conflict.translation_conflict ? ` · ${t('translation_collections.translation_conflict')}` : ''}
      </Text>)}</Stack>
    </Alert>}
    {(inspection.diagnostics || []).map((item, index) => <Alert key={`${item.code}-${index}`} color={item.severity === 'error' ? 'red' : 'yellow'} title={`${item.code} · ${item.severity}`}>{item.message}</Alert>)}
    {!inspection.can_export && <Text size="sm">{t('translation_collections.preview_blocked')}</Text>}
  </Stack>;
}
