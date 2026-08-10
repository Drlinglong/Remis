import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  Grid,
  Group,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Tooltip,
  NativeSelect,
  MultiSelect,
} from '@mantine/core';
import {
  IconAdjustments,
  IconAlertCircle,
  IconSettings,
} from '@tabler/icons-react';

import EmbeddedWorkshopSettingsCard from './EmbeddedWorkshopSettingsCard';
import LanguageTargetSelector from './LanguageTargetSelector';
import ResumeSettingsCard from './ResumeSettingsCard';
import CollapsibleSettingsCard from './CollapsibleSettingsCard';
import layoutStyles from '../layout/Layout.module.css';
import { FEATURES } from '../../config/features';
import {
  buildModelOptions,
  findLanguageByCode,
  resolveGameName,
  TRANSLATION_CONTEXT_MODES,
} from '../../utils/initialTranslation';

export default function ConfigStep({
  availableGlossaries,
  availableModels,
  checkpointHintInfo,
  config,
  embeddedWorkshopModels,
  form,
  onSubmit,
  selectedProject,
  selectedProjectId,
  t,
}) {
  const translationBatchOptions = [
    { value: '', label: t('translation_page.translation_limit_auto', { defaultValue: 'Auto (Recommended)' }) },
    { value: '5', label: '5' },
    { value: '10', label: '10' },
    { value: '20', label: '20' },
    { value: '40', label: '40' },
    { value: '60', label: '60' },
  ];
  const translationConcurrencyOptions = [
    { value: '', label: t('translation_page.translation_limit_auto', { defaultValue: 'Auto (Recommended)' }) },
    { value: '1', label: '1' },
    { value: '2', label: '2' },
    { value: '4', label: '4' },
    { value: '8', label: '8' },
    { value: '12', label: '12' },
    { value: '16', label: '16' },
  ];
  const translationRpmOptions = ['10', '20', '40', '60', '80', '120'].map((value) => ({ value, label: value }));

  const renderInfoLabel = (title, tooltip) => (
    <Group gap={4} wrap="nowrap">
      <Text size="sm" c="var(--text-main)">
        {title}
      </Text>
      {tooltip && (
        <Tooltip label={tooltip} multiline w={320} withArrow>
          <ThemeIcon variant="subtle" color="gray" size="sm" style={{ cursor: 'help' }}>
            <IconAlertCircle size={14} />
          </ThemeIcon>
        </Tooltip>
      )}
    </Group>
  );

  const renderNativeSelect = ({
    label, value, onChange, options, description, allowEmpty = true,
  }) => (
    <NativeSelect
      label={label}
      value={value}
      onChange={onChange}
      data={[
        ...(allowEmpty ? [{ value: '', label: t('common.select', 'Select') }] : []),
        ...options.map(o => ({ value: o.value, label: o.label }))
      ]}
      description={description}
      styles={{
        input: {
          minHeight: 40,
          borderRadius: 10,
          border: '1px solid var(--glass-border)',
          background: 'var(--glass-bg)',
          color: 'var(--text-main)',
          boxShadow: 'var(--shadow-elevation)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          transition: 'all 150ms ease',
        },
        description: {
          marginTop: 6,
        }
      }}
    />
  );

  const sourceLanguageCode = selectedProject?.source_language;
  const providerOptions = config.api_providers
    .filter((provider) => provider.value !== 'hunyuan' || FEATURES.ENABLE_HUNYUAN_PROVIDER)
    .map((provider) => ({
      value: provider.value,
      label: provider.label,
    }));

  const modelOptions = availableModels.map((model) => ({
    value: model.value,
    label: model.label,
  }));

  const glossaryOptions = availableGlossaries.map((glossary) => ({
    value: glossary.value,
    label: glossary.label,
  }));
  const contextModeOptions = [
    {
      value: TRANSLATION_CONTEXT_MODES.NONE,
      label: t('translation_context_mode.none'),
    },
    {
      value: TRANSLATION_CONTEXT_MODES.GLOSSARIES,
      label: t('translation_context_mode.glossaries'),
    },
    {
      value: TRANSLATION_CONTEXT_MODES.ARCHIVE,
      label: t('translation_context_mode.archive'),
    },
  ];

  const resolvedWorkshopModels = form.values.embedded_workshop_follow_primary_settings
    ? embeddedWorkshopModels
    : buildModelOptions(form.values.embedded_workshop_api_provider, config.api_providers);

  const embeddedWorkshopModelOptions = resolvedWorkshopModels.map((model) => ({
    value: model.value,
    label: model.label,
  }));

  const disguiseOptions = Object.values(config.languages).map((language) => ({
    value: language.key,
    label: `${language.name} (${language.key})`,
  }));

  const [showAdvancedOptions, setShowAdvancedOptions] = React.useState(false);

  return (
    <form id="initial-translation-config-form" onSubmit={form.onSubmit(onSubmit)}>
      <Grid gutter="xl">
        <Grid.Col span={{ base: 12, md: showAdvancedOptions ? 5 : 8 }}>
          <Card
            id="translation-config-card"
            withBorder
            padding="xl"
            radius="md"
            className={layoutStyles.glassCard}
            data-remis-surface="surface"
            h="100%"
          >
            <Stack gap="md">
              <Group>
                <ThemeIcon size="lg" radius="md" variant="light" color="blue">
                  <IconSettings size={20} />
                </ThemeIcon>
                <Text size="lg" fw={500}>{t('initial_translation_step_core_settings')}</Text>
              </Group>

              {selectedProjectId && (
                <TextInput
                  label={t('form_label_project_name')}
                  value={selectedProject?.label || 'Unknown'}
                  readOnly
                  aria-readonly="true"
                  variant="filled"
                />
              )}

              {selectedProjectId && (
                <Grid>
                  <Grid.Col span={6}>
                    <Tooltip label={t('initial_translation_step_readonly_hint')} withArrow>
                      <div>
                        <TextInput
                          label={t('form_label_game')}
                          value={selectedProject ? resolveGameName(config.game_profiles, selectedProject.game_id) : 'Unknown'}
                          readOnly
                          aria-readonly="true"
                          variant="filled"
                        />
                      </div>
                    </Tooltip>
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Tooltip label={t('initial_translation_step_readonly_hint')} withArrow>
                      <div>
                        <TextInput
                          label={t('form_label_source_language')}
                          value={selectedProject ? (findLanguageByCode(config.languages, selectedProject.source_language)?.name || 'Unknown') : 'Unknown'}
                          readOnly
                          aria-readonly="true"
                          variant="filled"
                        />
                      </div>
                    </Tooltip>
                  </Grid.Col>
                </Grid>
              )}

              {!form.values.english_disguise && (
                <LanguageTargetSelector
                  form={form}
                  languages={config.languages}
                  sourceLanguageCode={sourceLanguageCode}
                  t={t}
                />
              )}

              {renderNativeSelect({
                label: t('form_label_api_provider'),
                value: form.values.api_provider,
                options: providerOptions,
                onChange: (event) => form.setFieldValue('api_provider', event.currentTarget.value),
              })}

              {!['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'hunyuan'].includes(form.values.api_provider) && (
                <Tooltip label={t('tutorial.api_key_warning_tooltip')} multiline w={340} withArrow>
                  <Group gap={4} mt={-6} style={{ width: 'fit-content', cursor: 'help' }}>
                    <IconAlertCircle size={14} color="orange" />
                    <Text size="xs" c="orange">
                      {t('tutorial.api_key_warning_label')}
                    </Text>
                  </Group>
                </Tooltip>
              )}

              {['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga'].includes(form.values.api_provider) && (
                <Alert variant="light" color="yellow" title={t('tutorial.local_llm_warning')} icon={<IconAlertCircle size={16} />} mt="xs" />
              )}

              {availableModels.length > 0 && (
                <Group align="flex-end" gap={5} style={{ width: '100%' }}>
                  <Box style={{ flex: 1 }}>
                    {renderNativeSelect({
                      label: t('initial_translation_step_model'),
                      value: form.values.model_name,
                      options: modelOptions,
                      onChange: (event) => form.setFieldValue('model_name', event.currentTarget.value),
                    })}
                  </Box>
                  <Tooltip label={t('model_settings_hint', 'You can add more models in Settings > API Settings')} withArrow>
                    <ThemeIcon variant="light" color="gray" size="lg" mb={2}>
                      <IconSettings size={18} />
                    </ThemeIcon>
                  </Tooltip>
                </Group>
              )}
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: showAdvancedOptions ? 7 : 4 }}>
          <CollapsibleSettingsCard
            accent="orange"
            icon={<IconAdjustments size={20} />}
            isOpen={showAdvancedOptions}
            keepMounted
            onToggle={() => setShowAdvancedOptions((value) => !value)}
            t={t}
            title={t('advanced_options', 'Advanced Options')}
            toggleAriaLabel={t('advanced_options', 'Advanced Options')}
            description={t('translation_page.translation_limit_auto', { defaultValue: 'Auto (Recommended)' })}
          >
            <Stack gap="md">
              <Textarea
                label={t('form_label_additional_prompt')}
                placeholder={t('form_placeholder_additional_prompt')}
                autosize
                minRows={4}
                {...form.getInputProps('mod_context')}
              />

              <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
                <Box style={{ flex: 1 }}>
                  {renderNativeSelect({
                    label: renderInfoLabel(
                      t('translation_page.translation_batch_size', { defaultValue: '每批翻译条数' }),
                      t('translation_page.translation_batch_size_tooltip', { defaultValue: '控制每次送给 AI 的文本条目数量。只对本次翻译生效。较小更稳，较大通常更快。' }),
                    ),
                    value: form.values.translation_batch_size_limit,
                    options: translationBatchOptions,
                    onChange: (event) => form.setFieldValue('translation_batch_size_limit', event.currentTarget.value),
                  })}
                </Box>
                <Box style={{ flex: 1 }}>
                  {renderNativeSelect({
                    label: renderInfoLabel(
                      t('incremental_translation.concurrency_limit'),
                      t('translation_page.translation_concurrency_tooltip', { defaultValue: '控制同时向 AI 发起多少个翻译批次。只对本次翻译生效。本地模型建议设低一点。' }),
                    ),
                    value: form.values.translation_concurrency_limit,
                    options: translationConcurrencyOptions,
                    onChange: (event) => form.setFieldValue('translation_concurrency_limit', event.currentTarget.value),
                  })}
                </Box>
                <Box style={{ flex: 1 }}>
                  {renderNativeSelect({
                    label: renderInfoLabel(
                      t('incremental_translation.rpm_limit'),
                      t('translation_page.translation_rpm_tooltip', { defaultValue: '限制每分钟请求数。只对本次翻译生效，可用于避免接口限流或本地服务过载。' }),
                    ),
                    value: form.values.translation_rpm_limit,
                    options: translationRpmOptions,
                    onChange: (event) => form.setFieldValue('translation_rpm_limit', event.currentTarget.value),
                  })}
                </Box>
              </SimpleGrid>

              {renderNativeSelect({
                label: t('translation_context_mode.label'),
                description: t('translation_context_mode.description'),
                value: form.values.translation_context_mode,
                options: contextModeOptions,
                allowEmpty: false,
                onChange: (event) => form.setFieldValue(
                  'translation_context_mode',
                  event.currentTarget.value,
                ),
              })}

              <Group grow align="flex-start">
                <Stack gap="xs">
                  <Tooltip
                    label={t('tooltip_clean_source', 'WARNING: This will DELETE all files in the uploaded mod folder except for localization files (.yml), Customizable Localization (.txt) and metadata (.mod, .json, .png) to save disk space. Use with caution!')}
                    multiline
                    w={300}
                    withArrow
                    color="red"
                  >
                    <div>
                      <Switch
                        label={t('form_label_clean_source')}
                        description={t('warning_clean_source')}
                        color="red"
                        checked={form.values.clean_source}
                        onChange={(event) => form.setFieldValue('clean_source', event.currentTarget.checked)}
                        style={{ cursor: 'help' }}
                      />
                    </div>
                  </Tooltip>
                </Stack>

                <Box style={{ flex: 1 }}>
                  <MultiSelect
                    label={t('form_label_extra_glossaries')}
                    placeholder={t('common.select', 'Select')}
                    data={glossaryOptions}
                    value={(form.values.selected_glossary_ids || []).map(String)}
                    onChange={(values) => form.setFieldValue('selected_glossary_ids', values.map(Number))}
                    searchable
                    clearable
                    disabled={form.values.translation_context_mode === TRANSLATION_CONTEXT_MODES.NONE}
                    styles={{
                      input: {
                        minHeight: 40,
                        borderRadius: 10,
                        border: '1px solid var(--glass-border)',
                        background: 'var(--glass-bg)',
                        color: 'var(--text-main)',
                        boxShadow: 'var(--shadow-elevation)',
                        backdropFilter: 'blur(12px)',
                        WebkitBackdropFilter: 'blur(12px)',
                      }
                    }}
                  />
                </Box>
              </Group>

              {checkpointHintInfo && !form.values.use_resume && (
                <Alert color="yellow" variant="light" radius="md" title={t('translation_page.resume_hint.title', { defaultValue: '检测到可用断点' })}>
                  <Stack gap={6}>
                    <Text size="sm">
                      {t('translation_page.resume_hint.desc', {
                        defaultValue: '检测到上次中断的翻译记录，您可以开启断点续传直接接着跑。',
                        count: checkpointHintInfo.completed_count ?? 0,
                      })}
                    </Text>
                    <Group>
                      <Button size="xs" variant="light" onClick={() => form.setFieldValue('use_resume', true)}>
                        {t('translation_page.resume_hint.enable', { defaultValue: '开启断点续传' })}
                      </Button>
                    </Group>
                  </Stack>
                </Alert>
              )}

              <ResumeSettingsCard
                checkpointHintInfo={checkpointHintInfo}
                form={form}
                t={t}
              />

              <EmbeddedWorkshopSettingsCard
                config={config}
                embeddedWorkshopModelOptions={embeddedWorkshopModelOptions}
                form={form}
                providerOptions={providerOptions}
                renderInfoLabel={renderInfoLabel}
                renderNativeSelect={renderNativeSelect}
                t={t}
              />

              <Card withBorder p="md" radius="md" bg="var(--mantine-color-body)">
                <Stack gap="xs">
                  <Switch
                    label={t('form_label_disguise_mode')}
                    description={t('form_desc_disguise_mode')}
                    {...form.getInputProps('english_disguise', {
                      type: 'checkbox',
                      onChange: (event) => {
                        form.setFieldValue('english_disguise', event.currentTarget.checked);
                        if (event.currentTarget.checked) {
                          form.setFieldValue('target_lang_codes', []);
                        } else {
                          form.setFieldValue('custom_name', '');
                          form.setFieldValue('custom_key', '');
                          form.setFieldValue('custom_prefix', '');
                          form.setFieldValue('disguise_target_key', '');
                        }
                      },
                    })}
                  />

                  {form.values.english_disguise && (
                    <>
                      <Text size="sm" fw={500} mt="xs">{t('form_title_custom_config')}</Text>
                      <TextInput
                        label={t('form_label_custom_name')}
                        placeholder={t('form_placeholder_custom_name')}
                        description={t('form_desc_custom_name')}
                        {...form.getInputProps('custom_name')}
                      />
                      <Group grow>
                        <Box style={{ flex: 1 }}>
                          {renderNativeSelect({
                            label: t('form_label_disguise_target'),
                            value: form.values.disguise_target_key,
                            options: disguiseOptions,
                            onChange: (event) => {
                              const value = event.currentTarget.value;
                              form.setFieldValue('disguise_target_key', value);
                              form.setFieldValue('custom_key', value);
                            },
                          })}
                        </Box>
                        <TextInput
                          label={t('form_label_folder_prefix')}
                          placeholder={t('form_placeholder_folder_prefix')}
                          {...form.getInputProps('custom_prefix')}
                        />
                      </Group>
                    </>
                  )}
                </Stack>
              </Card>
            </Stack>
          </CollapsibleSettingsCard>
        </Grid.Col>
      </Grid>

    </form>
  );
}
