import React from 'react';
import {
  Box,
  Button,
  Group,
  Text,
  ThemeIcon,
} from '@mantine/core';
import {
  IconCheck,
  IconLanguage,
} from '@tabler/icons-react';

import controlsStyles from './InitialTranslationControls.module.css';

function marsLanguageName(code, fallback, t) {
  if (code === 'es') return t('mars_pipeline.language_es_spain', 'Spanish (Spain)');
  if (code === 'pt-BR') return t('mars_pipeline.language_pt_br', 'Portuguese (Brazil)');
  return fallback;
}

export default function LanguageTargetSelector({
  form,
  languages,
  gameId,
  supportedLanguageCodes,
  sourceLanguageCode,
  t,
}) {
  const isSurvivingMars = gameId === 'surviving_mars';
  const allowedLanguageCodes = React.useMemo(() => {
    if (!isSurvivingMars || !Array.isArray(supportedLanguageCodes)) return null;
    return new Set(supportedLanguageCodes || []);
  }, [isSurvivingMars, supportedLanguageCodes]);
  const languageOptions = React.useMemo(() => Object.values(languages || {})
    .filter((language) => (
      language.code !== sourceLanguageCode
      && (!allowedLanguageCodes || allowedLanguageCodes.has(language.code))
    ))
    .map((language) => ({
      value: language.code,
      label: isSurvivingMars
        ? marsLanguageName(language.code, language.name, t)
        : language.name,
    })), [allowedLanguageCodes, isSurvivingMars, languages, sourceLanguageCode, t]);
  const eligibleTargetCodes = React.useMemo(
    () => new Set(languageOptions.map((language) => language.value)),
    [languageOptions]
  );
  const selectedTargets = React.useMemo(
    () => form.values.target_lang_codes || [],
    [form.values.target_lang_codes]
  );
  const selectedTargetCount = selectedTargets.length;
  const hasLanguageCatalog = Object.keys(languages || {}).length > 0;

  React.useEffect(() => {
    if (!hasLanguageCatalog) {
      if (sourceLanguageCode && selectedTargets.includes(sourceLanguageCode)) {
        form.setFieldValue(
          'target_lang_codes',
          selectedTargets.filter((code) => code !== sourceLanguageCode)
        );
      }
      return;
    }
    const filteredTargets = selectedTargets.filter((code) => (
      code !== sourceLanguageCode && eligibleTargetCodes.has(code)
    ));
    if (filteredTargets.length === selectedTargets.length) return;
    form.setFieldValue(
      'target_lang_codes',
      filteredTargets
    );
  }, [eligibleTargetCodes, form, hasLanguageCatalog, selectedTargets, sourceLanguageCode]);

  const toggleSelection = (languageCode) => {
    if (selectedTargets.includes(languageCode)) {
      form.setFieldValue(
        'target_lang_codes',
        selectedTargets.filter((code) => code !== languageCode)
      );
      return;
    }
    form.clearFieldError('target_lang_codes');
    form.setFieldValue('target_lang_codes', [...selectedTargets, languageCode]);
  };

  const selectAllTargets = () => {
    form.clearFieldError('target_lang_codes');
    form.setFieldValue(
      'target_lang_codes',
      languageOptions.map((language) => language.value)
    );
  };

  return (
    <Box className={controlsStyles.targetLanguageSection}>
      <Group justify="space-between" align="flex-start" gap="sm">
        <Group gap="sm" align="flex-start">
          <ThemeIcon variant="light" color="cyan" radius="md">
            <IconLanguage size={18} />
          </ThemeIcon>
          <Box>
            <Text fw={700} c="var(--text-main)">
              {t('initial_translation_target_section_title')}
            </Text>
            <Text
              size="sm"
              c={selectedTargetCount > 0 ? 'cyan' : 'orange'}
              fw={600}
            >
              {selectedTargetCount > 0
                ? t('initial_translation_target_selected_count', { count: selectedTargetCount })
                : t('initial_translation_target_none')}
            </Text>
          </Box>
        </Group>
        <Group gap={4}>
          <Button
            type="button"
            size="compact-xs"
            variant="subtle"
            onClick={selectAllTargets}
            disabled={selectedTargetCount === languageOptions.length}
          >
            {t('initial_translation_select_all')}
          </Button>
          <Button
            type="button"
            size="compact-xs"
            variant="subtle"
            color="gray"
            onClick={() => form.setFieldValue('target_lang_codes', [])}
            disabled={selectedTargetCount === 0}
          >
            {t('initial_translation_clear_all')}
          </Button>
        </Group>
      </Group>

      <Group gap="xs" mt="md">
        {languageOptions.map((language) => {
          const checked = selectedTargets.includes(language.value);
          return (
            <Button
              key={language.value}
              type="button"
              size="compact-sm"
              variant={checked ? 'light' : 'default'}
              color={checked ? 'cyan' : 'gray'}
              rightSection={checked ? <IconCheck size={14} /> : null}
              aria-pressed={checked}
              className={controlsStyles.languageChip}
              onClick={() => toggleSelection(language.value)}
            >
              {language.label}
            </Button>
          );
        })}
      </Group>

      {selectedTargetCount === 0 && (
        <Text size="xs" c="orange" mt="sm" role="alert">
          {t('initial_translation_target_required')}
        </Text>
      )}
    </Box>
  );
}
