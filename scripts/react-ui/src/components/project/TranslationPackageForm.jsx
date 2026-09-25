import React from 'react';
import { Button, Select, Stack, Text, TextInput } from '@mantine/core';

const asOptions = (values, getLabel) => (Array.isArray(values) ? values : []).map((value) => ({
  value: value.code || value.output_folder_name || '',
  label: getLabel(value),
})).filter((option) => option.value);

export default function TranslationPackageForm({ packageFlow, t }) {
  const outputs = packageFlow.options?.translation_outputs || [];
  const languages = packageFlow.options?.languages || [];
  const sourceMetadataComplete = Boolean(packageFlow.options?.source_mod?.id || packageFlow.sourceModId.trim())
    && Boolean(packageFlow.options?.source_mod?.title || packageFlow.sourceModTitle.trim());
  const editingDisabled = packageFlow.generating;

  return (
    <Stack gap="md">
      <Select
        label={t('mars_translation_package.output_label')}
        data={asOptions(outputs, (output) => `${output.output_folder_name} — ${output.path}`)}
        value={packageFlow.outputFolderName || null}
        onChange={(value) => packageFlow.updateField('outputFolderName', value || '')}
        searchable
        nothingFoundMessage={t('mars_translation_package.no_outputs')}
        disabled={outputs.length === 0 || editingDisabled}
      />
      {outputs.length === 0 && <Text size="sm" c="dimmed">{t('mars_translation_package.no_outputs')}</Text>}
      <Select
        label={t('mars_translation_package.language_label')}
        data={asOptions(languages, (language) => `${language.name} (${language.game_language || language.code})`)}
        value={packageFlow.targetLanguage || null}
        onChange={(value) => packageFlow.updateField('targetLanguage', value || '')}
        disabled={languages.length === 0 || editingDisabled}
      />
      {languages.length === 0 && <Text size="sm" c="dimmed">{t('mars_translation_package.no_languages')}</Text>}
      {!packageFlow.options.source_mod?.id && (
        <TextInput
          label={t('mars_translation_package.source_mod_id_label')}
          value={packageFlow.sourceModId}
          onChange={(event) => packageFlow.updateField('sourceModId', event.currentTarget.value)}
          disabled={editingDisabled}
        />
      )}
      {!packageFlow.options.source_mod?.title && (
        <TextInput
          label={t('mars_translation_package.source_mod_title_label')}
          value={packageFlow.sourceModTitle}
          onChange={(event) => packageFlow.updateField('sourceModTitle', event.currentTarget.value)}
          disabled={editingDisabled}
        />
      )}
      <TextInput
        label={t('mars_translation_package.author_label')}
        value={packageFlow.author}
        onChange={(event) => packageFlow.updateField('author', event.currentTarget.value)}
        disabled={editingDisabled}
      />
      <Text size="sm" c="dimmed">{t('mars_translation_package.source_assets_notice')}</Text>
      <Button
        onClick={packageFlow.createPlan}
        loading={packageFlow.planning}
        disabled={!packageFlow.outputFolderName || !packageFlow.targetLanguage || !sourceMetadataComplete
          || packageFlow.loading || editingDisabled}
      >
        {t('mars_translation_package.preview')}
      </Button>
    </Stack>
  );
}
