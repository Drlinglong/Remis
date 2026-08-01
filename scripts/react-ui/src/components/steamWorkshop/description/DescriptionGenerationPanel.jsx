import React, { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  Paper,
  Stack,
  Text,
} from '@mantine/core';
import { IconSparkles } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { DescriptionGenerationSettings } from './DescriptionGenerationSettings';
import { useDescriptionModelConfig } from './useDescriptionModelConfig';

export function DescriptionGenerationPanel({
  isGenerating,
  onGenerate,
  workshopItemId,
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const [approved, setApproved] = useState(false);
  const [language, setLanguage] = useState('zh-CN');
  // Initialize once so language changes and unrelated renders never overwrite
  // a template the user has already edited.
  const [userTemplate, setUserTemplate] = useState(
    () => t('steam_workshop.generation_default_template'),
  );
  const {
    isLoading: isConfigLoading,
    languageOptions,
    loadConfig,
    loadError,
    model,
    modelOptions,
    missingApiKey,
    provider,
    providerOptions,
    setModel,
    setProvider,
  } = useDescriptionModelConfig();

  const selectedLanguage = languageOptions.find((item) => item.value === language) || null;
  const selectedProvider = providerOptions.find((item) => item.value === provider) || null;
  const hasLanguages = languageOptions.length > 0;

  useEffect(() => {
    if (languageOptions.length === 0) return;
    if (languageOptions.some((item) => item.value === language)) return;
    setLanguage(
      languageOptions.find((item) => item.value === 'zh-CN')?.value
      || languageOptions[0].value,
    );
  }, [language, languageOptions]);

  const closeModal = () => {
    setOpened(false);
    setApproved(false);
  };

  const handleGenerate = async () => {
    const created = await onGenerate({
      approved,
      language,
      model,
      provider,
      target_language_name: selectedLanguage?.label || '',
      user_template: userTemplate,
    });
    if (created) {
      closeModal();
    }
  };

  const canGenerate = Boolean(
    workshopItemId
    && provider
    && model
    && !missingApiKey
    && selectedLanguage
    && userTemplate.trim(),
  );
  const hasProviders = providerOptions.length > 0;
  const hasModels = modelOptions.length > 0;
  const canOpenGeneration = Boolean(
    workshopItemId
    && !isConfigLoading
    && !loadError
    && hasProviders
    && hasModels
    && !missingApiKey
    && selectedLanguage,
  );

  const handleProviderChange = (value) => {
    setProvider(value || '');
    setApproved(false);
  };

  const handleModelChange = (value) => {
    setModel(value || '');
    setApproved(false);
  };

  const handleLanguageChange = (value) => {
    setLanguage(value || '');
    setApproved(false);
  };

  const handleTemplateChange = (event) => {
    setUserTemplate(event.currentTarget.value);
    setApproved(false);
  };

  return (
    <Paper withBorder p="md" data-remis-surface="paper">
      <Group justify="space-between" align="flex-start">
        <div style={{ minWidth: 0 }}>
          <Text fw={700}>{t('steam_workshop.generate_candidate_title')}</Text>
          <Text c="dimmed" size="sm">
            {workshopItemId
              ? t('steam_workshop.generate_candidate_desc', { workshopId: workshopItemId })
              : t('steam_workshop.generate_candidate_requires_id')}
          </Text>
        </div>
        <Button
          variant="light"
          leftSection={<IconSparkles size={16} />}
          loading={isConfigLoading || isGenerating}
          disabled={!canOpenGeneration}
          onClick={() => {
            setApproved(false);
            setOpened(true);
          }}
        >
          {t('steam_workshop.model_generate')}
        </Button>
      </Group>

      <DescriptionGenerationSettings
        hasLanguages={hasLanguages}
        hasModels={hasModels}
        hasProviders={hasProviders}
        isConfigLoading={isConfigLoading}
        language={language}
        languageOptions={languageOptions}
        loadError={loadError}
        loadConfig={loadConfig}
        missingApiKey={missingApiKey}
        model={model}
        modelOptions={modelOptions}
        onLanguageChange={handleLanguageChange}
        onModelChange={handleModelChange}
        onProviderChange={handleProviderChange}
        onTemplateChange={handleTemplateChange}
        provider={provider}
        providerOptions={providerOptions}
        selectedLanguage={selectedLanguage}
        userTemplate={userTemplate}
      />

      <Modal
        opened={opened}
        onClose={closeModal}
        data-remis-surface="elevated"
        title={t('steam_workshop.confirm_model_generation')}
        size="lg"
      >
        <Stack data-remis-surface="elevated">
          <Alert color="yellow" title={t('steam_workshop.model_call_summary')}>
            <Stack gap="xs">
              <Text size="sm"><strong>{t('steam_workshop.workshop_id_label')}</strong>{workshopItemId}</Text>
              <Text size="sm"><strong>{t('steam_workshop.api_provider_label')}</strong>{selectedProvider?.label || provider || t('steam_workshop.not_selected')}</Text>
              <Text size="sm"><strong>{t('steam_workshop.model_label')}</strong>{model || t('steam_workshop.not_selected')}</Text>
              <Text size="sm"><strong>{t('steam_workshop.description_language_label')}</strong>{selectedLanguage?.label || t('steam_workshop.not_selected')}</Text>
              <Text size="sm" c="dimmed">
                {t('steam_workshop.model_call_notice')}
              </Text>
            </Stack>
          </Alert>
          <Checkbox
            checked={approved}
            onChange={(event) => setApproved(event.currentTarget.checked)}
            label={t('steam_workshop.model_call_approval')}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeModal}>{t('steam_workshop.cancel')}</Button>
            <Button
              loading={isGenerating}
              disabled={!approved || !canGenerate}
              onClick={handleGenerate}
            >
              {t('steam_workshop.confirm_generate')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Paper>
  );
}
