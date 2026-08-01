import React from 'react';
import {
  Alert,
  Button,
  Group,
  Select,
  SimpleGrid,
  Text,
  Textarea,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';

export function DescriptionGenerationSettings({
  hasLanguages,
  hasModels,
  hasProviders,
  isConfigLoading,
  language,
  languageOptions,
  loadError,
  loadConfig,
  missingApiKey,
  model,
  modelOptions,
  onLanguageChange,
  onModelChange,
  onProviderChange,
  onTemplateChange,
  provider,
  providerOptions,
  selectedLanguage,
  userTemplate,
}) {
  const { t } = useTranslation();
  return (
    <>
      {isConfigLoading && (
        <Alert color="blue" title={t('steam_workshop.loading_api_configuration')}>
          {t('steam_workshop.loading_api_configuration_desc')}
        </Alert>
      )}
      {loadError && (
        <Alert
          color="red"
          title={t('steam_workshop.api_configuration_load_failed')}
          withCloseButton={false}
        >
          <Group justify="space-between" align="center">
            <Text size="sm">{loadError}</Text>
            <Button variant="light" color="red" size="xs" onClick={loadConfig}>
              {t('steam_workshop.retry')}
            </Button>
          </Group>
        </Alert>
      )}
      {!isConfigLoading && !loadError && !hasProviders && (
        <Alert color="blue" title={t('steam_workshop.no_api_provider')}>
          {t('steam_workshop.no_api_provider_desc')}
        </Alert>
      )}
      {!isConfigLoading && !loadError && hasProviders && provider && !hasModels && (
        <Alert color="blue" title={t('steam_workshop.no_models')}>
          {t('steam_workshop.no_models_desc')}
        </Alert>
      )}
      {!isConfigLoading && !loadError && hasProviders && provider && hasModels && missingApiKey && (
        <Alert color="yellow" title={t('steam_workshop.no_api_key')}>
          {t('steam_workshop.no_api_key_desc')}
        </Alert>
      )}
      {!isConfigLoading && !loadError && !hasLanguages && (
        <Alert color="blue" title={t('steam_workshop.no_description_languages')}>
          {t('steam_workshop.no_description_languages_desc')}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Select
          label={t('steam_workshop.api_provider')}
          placeholder={isConfigLoading ? t('steam_workshop.loading_configuration') : t('steam_workshop.select_api_provider')}
          data={providerOptions}
          value={provider || null}
          title={provider || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !hasProviders}
          onChange={onProviderChange}
        />
        <Select
          label={t('steam_workshop.model')}
          placeholder={
            isConfigLoading
              ? t('steam_workshop.loading_configuration')
              : !hasProviders
                ? t('steam_workshop.configure_api_provider_first')
                : hasModels
                  ? t('steam_workshop.select_model')
                  : t('steam_workshop.no_models')
          }
          data={modelOptions}
          value={model || null}
          title={model || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !provider || !hasModels}
          onChange={onModelChange}
        />
        <Select
          label={t('steam_workshop.description_language')}
          description={t('steam_workshop.description_language_desc')}
          placeholder={isConfigLoading ? t('steam_workshop.loading_configuration') : t('steam_workshop.select_description_language')}
          data={languageOptions}
          value={language || null}
          title={selectedLanguage?.label || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !hasLanguages}
          onChange={onLanguageChange}
        />
      </SimpleGrid>

      <Textarea
        label={t('steam_workshop.publishing_template')}
        description={t('steam_workshop.publishing_template_desc')}
        minRows={8}
        value={userTemplate}
        onChange={onTemplateChange}
      />
    </>
  );
}
