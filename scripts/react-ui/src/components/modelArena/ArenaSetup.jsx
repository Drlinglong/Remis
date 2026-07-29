import React from 'react';
import {
  ActionIcon,
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowsShuffle,
  IconBook2,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';

import { buildModelArenaModelOptions } from '../../services/modelArenaService';

const providerValue = (provider) => provider.value || provider.id || '';
const providerLabel = (provider) => provider.label || provider.name || providerValue(provider);
const featureTagLabel = (tag, t) => {
  if (tag.startsWith('length:')) {
    return t(`model_arena.feature_length_${tag.slice('length:'.length)}`, {
      defaultValue: tag,
    });
  }
  if (tag.startsWith('file:')) {
    return t('model_arena.feature_file', {
      file: tag.slice('file:'.length),
      defaultValue: tag,
    });
  }
  return t(`model_arena.feature_${tag}`, { defaultValue: tag });
};

export default function ArenaSetup({
  t,
  projects,
  providers,
  languages,
  values,
  onChange,
  draft,
  loading,
  onCreateDraft,
  onResample,
  onEditDraft,
  onRequestStart,
}) {
  const selectedProject = projects.find(
    (project) => String(project.project_id || project.value) === values.project_id,
  );
  const selectedPairs = new Set(values.contestants.map(
    (contestant) => `${contestant.provider_id}:${contestant.model_id}`,
  ));
  const isValid = Boolean(values.project_id && values.target_lang_code)
    && values.contestants.length >= 2
    && values.contestants.length <= 3
    && values.contestants.every((item) => item.provider_id && item.model_id)
    && values.contestants.every((item) => providers.find(
      (provider) => providerValue(provider) === item.provider_id,
    )?.configured !== false)
    && selectedPairs.size === values.contestants.length;

  const updateContestant = (index, patch) => {
    const next = values.contestants.map((item, itemIndex) => (
      itemIndex === index ? { ...item, ...patch } : item
    ));
    onChange({ contestants: next });
  };

  const languageOptions = Object.entries(languages || {}).map(([key, language]) => ({
    value: typeof language === 'string' ? key : language?.code || key,
    label: typeof language === 'string'
      ? language
      : language?.name || language?.name_en || language?.key || key,
  }));

  return (
    <Stack gap="lg">
      <div>
        <Title order={3}>{t('model_arena.setup_title')}</Title>
        <Text c="dimmed">{t('model_arena.setup_description')}</Text>
      </div>

      <SimpleGrid className="model-arena-basics-grid" cols={{ base: 1, md: 2, xl: 3 }}>
        <Select
          searchable
          required
          label={t('model_arena.project')}
          placeholder={projects.length ? t('model_arena.project_placeholder') : t('model_arena.no_projects')}
          data={projects.map((project) => ({
            value: String(project.project_id || project.value),
            label: project.name || project.label,
          }))}
          value={values.project_id}
          onChange={(projectId) => onChange({ project_id: projectId || '' })}
          disabled={Boolean(draft)}
        />
        <Select
          searchable
          required
          label={t('model_arena.target_language')}
          data={languageOptions}
          value={values.target_lang_code}
          onChange={(targetLanguage) => onChange({ target_lang_code: targetLanguage || '' })}
          disabled={Boolean(draft)}
        />
        <NumberInput
          label={t('model_arena.sample_count')}
          description={t('model_arena.sample_count_hint')}
          min={3}
          max={12}
          value={values.sample_size}
          onChange={(sampleSize) => onChange({ sample_size: Number(sampleSize) || 6 })}
          disabled={Boolean(draft)}
        />
      </SimpleGrid>
      {selectedProject && (
        <Group gap="xs">
          <Badge variant="light">{selectedProject.game_id || 'Mod'}</Badge>
          <Badge variant="outline">
            {t('form_label_source_language')}: {selectedProject.source_language || '—'}
          </Badge>
        </Group>
      )}

      <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
        <Group justify="space-between" mb="md">
          <div>
            <Text fw={700}>{t('model_arena.contestants')}</Text>
            <Text size="sm" c="dimmed">{t('model_arena.contestants_hint')}</Text>
          </div>
          <Badge variant="light">{values.contestants.length}/3</Badge>
        </Group>
        <Stack gap="sm">
          {values.contestants.map((contestant, index) => {
            const provider = providers.find(
              (item) => providerValue(item) === contestant.provider_id,
            );
            const models = buildModelArenaModelOptions(provider);
            return (
              <Group
                key={`contestant-${index}`}
                className="model-arena-contestant-row"
                align="flex-end"
                wrap="wrap"
              >
                <Select
                  className="model-arena-control"
                  required
                  searchable
                  label={t('model_arena.provider_number', { number: index + 1 })}
                  data={providers.map((item) => ({
                    value: providerValue(item),
                    label: item.configured === false
                      ? `${providerLabel(item)} · ${t('api_key_not_configured')}`
                      : providerLabel(item),
                    disabled: item.configured === false,
                  }))}
                  value={contestant.provider_id}
                  onChange={(value) => {
                    const nextProvider = providers.find((item) => providerValue(item) === value);
                    updateContestant(index, {
                      provider_id: value || '',
                      model_id: nextProvider?.selected_model
                        || buildModelArenaModelOptions(nextProvider)[0]
                        || '',
                    });
                  }}
                  disabled={Boolean(draft)}
                  style={{ flex: '1 1 18rem', minWidth: 0 }}
                />
                <Select
                  className="model-arena-control"
                  required
                  searchable
                  allowDeselect={false}
                  label={t('model_arena.model')}
                  placeholder={t('model_arena.model_placeholder')}
                  data={models.map((model) => ({ value: model, label: model }))}
                  value={contestant.model_id}
                  onChange={(value) => updateContestant(index, { model_id: value || '' })}
                  disabled={Boolean(draft) || !contestant.provider_id}
                  style={{ flex: '1.2 1 22rem', minWidth: 0 }}
                />
                {!draft && values.contestants.length > 2 && (
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    size="lg"
                    aria-label={t('model_arena.remove_model')}
                    onClick={() => onChange({
                      contestants: values.contestants.filter((_, itemIndex) => itemIndex !== index),
                    })}
                  >
                    <IconTrash size={18} />
                  </ActionIcon>
                )}
              </Group>
            );
          })}
        </Stack>
        {!draft && values.contestants.length < 3 && (
          <Button
            mt="md"
            variant="light"
            leftSection={<IconPlus size={16} />}
            onClick={() => onChange({
              contestants: [...values.contestants, { provider_id: '', model_id: '' }],
            })}
          >
            {t('model_arena.add_model')}
          </Button>
        )}
      </Card>

      <Checkbox
        checked={values.use_project_context}
        onChange={(event) => onChange({ use_project_context: event.currentTarget.checked })}
        label={t('model_arena.use_project_context')}
        disabled={Boolean(draft)}
      />

      {!isValid && !draft && (
        <Alert color="yellow" icon={<IconAlertCircle size={18} />}>
          {t('model_arena.setup_validation')}
        </Alert>
      )}

      {draft && (
        <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
          <Stack gap="md">
            <div>
              <Title order={4}>{t('model_arena.draft_ready')}</Title>
              <Text size="sm" c="dimmed" mt={4}>
                {t('model_arena.draft_summary', {
                  count: draft.sample_size || draft.samples?.length || values.sample_size,
                  eligible: draft.eligible_count ?? '—',
                  calls: draft.estimated_request_count
                    || (values.contestants.length * (draft.request_batch_count || 1)),
                })}
              </Text>
            </div>
            <Group gap="xs">
              <Badge variant="filled">
                {t('model_arena.sample_count_value', {
                  count: draft.samples?.length || draft.sample_size || 0,
                })}
              </Badge>
              <Badge variant="outline">
                {t('model_arena.seed', { seed: draft.sample_seed })}
              </Badge>
            </Group>
            <Text size="sm">
              {t('model_arena.batch_request_explanation', {
                models: values.contestants.length,
                samples: draft.samples?.length || draft.sample_size || 0,
              })}
            </Text>
            <Alert
              className="model-arena-glossary-alert"
              data-remis-surface="paper"
              color={draft.settings?.glossary_snapshot?.enabled ? 'blue' : 'yellow'}
              icon={<IconBook2 size={18} />}
              title={t('model_arena.glossary_snapshot_title')}
            >
              {draft.settings?.glossary_snapshot?.enabled ? (
                <Stack gap="xs">
                  <Text size="sm">
                    {t('model_arena.glossary_snapshot_summary', {
                      glossaries: draft.settings.glossary_snapshot.glossaries?.length || 0,
                      entries: draft.settings.glossary_snapshot.entry_count || 0,
                      matches: draft.settings.glossary_snapshot.matched_entry_count || 0,
                    })}
                  </Text>
                  <Group gap="xs">
                    {(draft.settings.glossary_snapshot.glossaries || []).map((glossary) => (
                      <Badge key={glossary.glossary_id} variant="outline">
                        {glossary.name} · {glossary.entry_count}
                      </Badge>
                    ))}
                  </Group>
                </Stack>
              ) : (
                <Text size="sm">{t('model_arena.glossary_snapshot_empty')}</Text>
              )}
            </Alert>
            <Text size="xs" c="dimmed">
              {t('model_arena.identity_hidden')}
            </Text>
            <Accordion variant="separated" className="model-arena-draft-samples">
              {(draft.samples || []).map((sample, index) => (
                <Accordion.Item key={sample.sample_id} value={sample.sample_id}>
                  <Accordion.Control>
                    <Group justify="space-between" wrap="nowrap">
                      <Text fw={700}>
                        {t('model_arena.output_sample', {
                          number: Number.isInteger(sample.ordinal)
                            ? sample.ordinal + 1
                            : index + 1,
                        })}
                      </Text>
                      <Group gap={4} wrap="wrap" justify="flex-end">
                        {(sample.feature_tags || []).map((tag) => (
                          <Badge key={tag} variant="outline" size="xs">
                            {featureTagLabel(tag, t)}
                          </Badge>
                        ))}
                      </Group>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <Text className="model-arena-source">{sample.source_text}</Text>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </Stack>
        </Card>
      )}

      <Group justify="flex-end">
        {draft ? (
          <>
            <Button variant="default" onClick={onEditDraft} disabled={loading}>
              {t('model_arena.edit_configuration')}
            </Button>
            <Button
              variant="default"
              leftSection={<IconArrowsShuffle size={17} />}
              onClick={onResample}
              loading={loading}
            >
              {t('model_arena.resample')}
            </Button>
            <Button onClick={onRequestStart}>{t('model_arena.start_arena')}</Button>
          </>
        ) : (
          <Button onClick={onCreateDraft} disabled={!isValid} loading={loading}>
            {t('model_arena.create_draft')}
          </Button>
        )}
      </Group>
    </Stack>
  );
}
