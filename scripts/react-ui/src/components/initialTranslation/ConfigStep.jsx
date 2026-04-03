import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
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
} from '@mantine/core';
import {
  IconAdjustments,
  IconAlertCircle,
  IconArrowLeft,
  IconChevronDown,
  IconChevronUp,
  IconClockHour4,
  IconRobot,
  IconSettings,
} from '@tabler/icons-react';

import layoutStyles from '../layout/Layout.module.css';
import { FEATURES } from '../../config/features';
import { buildModelOptions, findLanguageByCode, resolveGameName } from '../../utils/initialTranslation';

export default function ConfigStep({
  availableGlossaries,
  availableModels,
  checkpointHintInfo,
  config,
  embeddedWorkshopModels,
  form,
  onBack,
  onSubmit,
  selectedProject,
  selectedProjectId,
  t,
}) {
  const [showResumeDetails, setShowResumeDetails] = React.useState(false);
  const [showWorkshopSettings, setShowWorkshopSettings] = React.useState(false);

  const nativeSelectStyle = {
    width: '100%',
    minHeight: 40,
    padding: '10px 12px',
    borderRadius: 10,
    border: '1px solid var(--glass-border)',
    background: 'var(--glass-bg)',
    color: 'var(--text-main)',
    outline: 'none',
    boxShadow: 'var(--shadow-elevation)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    colorScheme: 'dark',
  };

  const sectionCardStyle = {
    background: 'linear-gradient(180deg, rgba(86, 111, 147, 0.16) 0%, rgba(41, 54, 72, 0.12) 100%)',
    border: '1px solid rgba(151, 177, 210, 0.16)',
  };

  const renderNativeSelect = ({ label, value, onChange, options, multiple = false, minHeight }) => (
    <Box>
      <Text size="sm" mb={6} c="var(--text-main)">
        {label}
      </Text>
      <select
        multiple={multiple}
        value={value}
        onChange={onChange}
        style={{
          ...nativeSelectStyle,
          minHeight: minHeight || (multiple ? 128 : 40),
        }}
      >
        {!multiple && <option value="">{t('common.select', 'Select')}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Box>
  );

  const renderCollapsibleCard = ({
    accent,
    action,
    children,
    description,
    disabled = false,
    icon,
    isOpen,
    onToggle,
    title,
  }) => (
    <Card withBorder p="md" radius="lg" style={sectionCardStyle}>
      <Stack gap="sm">
        {action}
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap="sm" align="flex-start" wrap="nowrap">
            <ThemeIcon size="lg" radius="md" variant="light" color={accent}>
              {icon}
            </ThemeIcon>
            <Box>
              <Text size="sm" fw={600} c="var(--text-main)">
                {title}
              </Text>
              <Text size="xs" c="dimmed" mt={2}>
                {description}
              </Text>
            </Box>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            color={accent}
            disabled={disabled}
            rightSection={isOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
            onClick={onToggle}
          >
            {isOpen
              ? t('common.collapse', { defaultValue: '收起' })
              : t('common.expand', { defaultValue: '展开' })}
          </Button>
        </Group>
        {isOpen && (
          <Box pt="sm" style={{ borderTop: '1px solid rgba(151, 177, 210, 0.14)' }}>
            {children}
          </Box>
        )}
      </Stack>
    </Card>
  );

  const languageOptions = Object.values(config.languages).map((language) => ({
    value: language.code,
    label: language.name,
  }));

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

  const toggleSelection = (field, itemValue) => {
    const currentValues = form.values[field] || [];
    if (currentValues.includes(itemValue)) {
      form.setFieldValue(field, currentValues.filter((value) => value !== itemValue));
      return;
    }
    form.setFieldValue(field, [...currentValues, itemValue]);
  };

  const renderCheckboxCardGroup = ({ description, field, label, options }) => (
    <Box>
      <Text size="sm" mb={6} c="var(--text-main)">
        {label}
      </Text>
      {description && (
        <Text size="xs" c="dimmed" mb="sm">
          {description}
        </Text>
      )}
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
        {options.map((option) => {
          const checked = (form.values[field] || []).includes(option.value);
          return (
            <Box
              key={option.value}
              onClick={() => toggleSelection(field, option.value)}
              style={{
                cursor: 'pointer',
                padding: '12px 14px',
                borderRadius: 12,
                border: checked ? '1px solid var(--text-highlight)' : '1px solid var(--glass-border)',
                background: checked ? 'rgba(120, 170, 220, 0.18)' : 'var(--glass-bg)',
                boxShadow: 'var(--shadow-elevation)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                transition: 'all 160ms ease',
              }}
            >
              <Group justify="space-between" wrap="nowrap">
                <Box>
                  <Text fw={600} c="var(--text-main)">
                    {option.label}
                  </Text>
                  {option.subLabel && (
                    <Text size="xs" c="dimmed" mt={2}>
                      {option.subLabel}
                    </Text>
                  )}
                </Box>
                <Checkbox
                  checked={checked}
                  onChange={() => toggleSelection(field, option.value)}
                  onClick={(event) => event.stopPropagation()}
                  color="blue"
                />
              </Group>
            </Box>
          );
        })}
      </SimpleGrid>
    </Box>
  );

  return (
    <form onSubmit={form.onSubmit(onSubmit)}>
      <Grid gutter="xl">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card id="translation-config-card" withBorder padding="xl" radius="md" className={layoutStyles.glassCard} h="100%">
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
                  disabled
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
                          disabled
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
                          disabled
                          variant="filled"
                        />
                      </div>
                    </Tooltip>
                  </Grid.Col>
                </Grid>
              )}

              {!form.values.english_disguise && renderCheckboxCardGroup({
                label: t('form_label_target_languages'),
                field: 'target_lang_codes',
                description: t('form_placeholder_target_languages'),
                options: languageOptions.map((language) => ({
                  ...language,
                  subLabel: config.languages[language.value]?.key,
                })),
              })}

              {renderNativeSelect({
                label: t('form_label_api_provider'),
                value: form.values.api_provider,
                options: providerOptions,
                onChange: (event) => form.setFieldValue('api_provider', event.currentTarget.value),
              })}

              {!['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'gemini_cli', 'hunyuan'].includes(form.values.api_provider) && (
                <Group gap={4} mt={-6}>
                  <IconAlertCircle size={14} color="orange" />
                  <Text size="xs" c="orange">
                    {t('tutorial.api_key_warning_label')}
                  </Text>
                </Group>
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

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder padding="xl" radius="md" className={layoutStyles.glassCard} h="100%">
            <Stack gap="md">
              <Group>
                <ThemeIcon size="lg" radius="md" variant="light" color="orange">
                  <IconAdjustments size={20} />
                </ThemeIcon>
                <Text size="lg" fw={500}>{t('advanced_options', 'Advanced Options')}</Text>
              </Group>

              <Textarea
                label={t('form_label_additional_prompt')}
                placeholder={t('form_placeholder_additional_prompt')}
                autosize
                minRows={4}
                {...form.getInputProps('mod_context')}
              />

              <Group grow align="flex-start">
                <Stack gap="xs">
                  <Switch
                    label={t('form_label_use_main_glossary')}
                    description={t('form_desc_use_main_glossary')}
                    {...form.getInputProps('use_main_glossary', { type: 'checkbox' })}
                  />
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
                  {renderNativeSelect({
                    label: t('form_label_extra_glossaries'),
                    value: form.values.selected_glossary_ids,
                    multiple: true,
                    minHeight: 140,
                    options: glossaryOptions,
                    onChange: (event) => {
                      const values = Array.from(event.currentTarget.selectedOptions, (option) => option.value);
                      form.setFieldValue('selected_glossary_ids', values);
                    },
                  })}
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

              {renderCollapsibleCard({
                accent: 'orange',
                icon: <IconClockHour4 size={18} />,
                isOpen: showResumeDetails,
                onToggle: () => setShowResumeDetails((value) => !value),
                title: t('translation_page.resume_detail_title', { defaultValue: '断点续传详情' }),
                description: t('translation_page.resume_detail_subtitle', { defaultValue: '默认收起。展开后可查看上次工作进行到什么时间、什么批次。' }),
                action: (
                  <Switch
                    label={t('form_label_use_resume')}
                    description={t('form_desc_use_resume')}
                    checked={form.values.use_resume}
                    onChange={(event) => form.setFieldValue('use_resume', event.currentTarget.checked)}
                  />
                ),
                children: checkpointHintInfo ? (
                  <Stack gap="xs">
                    {(checkpointHintInfo.targets || []).map((target) => (
                      <Card key={target.target_lang_code} withBorder p="sm" radius="md" bg="rgba(255,255,255,0.03)">
                        <Stack gap={4}>
                          <Text size="sm" fw={600} c="var(--text-main)">{target.target_lang_code}</Text>
                          <Text size="sm">
                            {t('translation_page.resume_detail_completed', {
                              defaultValue: '已完成文件：{{count}}',
                              count: target.completed_count ?? 0,
                            })}
                          </Text>
                          <Text size="sm">
                            {t('translation_page.resume_detail_batch', {
                              defaultValue: '上次批次：{{current}} / {{total}}',
                              current: target.metadata?.current_batch ?? 0,
                              total: target.metadata?.total_batches ?? 0,
                            })}
                          </Text>
                          <Text size="sm">
                            {t('translation_page.resume_detail_time', {
                              defaultValue: '上次保存：{{time}}',
                              time: target.last_saved_at || target.metadata?.last_saved_at || '--',
                            })}
                          </Text>
                          <Text size="sm">
                            {t('translation_page.resume_detail_file', {
                              defaultValue: '最后完成文件：{{file}}',
                              file: target.last_completed_file || target.metadata?.last_completed_file || '--',
                            })}
                          </Text>
                        </Stack>
                      </Card>
                    ))}
                    {(!checkpointHintInfo.targets || checkpointHintInfo.targets.length === 0) && (
                      <Text size="sm" c="dimmed">
                        {t('translation_page.resume_detail_empty', { defaultValue: '当前没有可展示的断点详情。' })}
                      </Text>
                    )}
                  </Stack>
                ) : (
                  <Text size="sm" c="dimmed">
                    {t('translation_page.resume_detail_none', { defaultValue: '没有未完成的工作。' })}
                  </Text>
                ),
              })}

              {renderCollapsibleCard({
                accent: 'blue',
                icon: <IconRobot size={18} />,
                isOpen: showWorkshopSettings,
                onToggle: () => setShowWorkshopSettings((value) => !value),
                title: t('translation_page.embedded_workshop_settings', { defaultValue: '智能工坊设置' }),
                description: t('translation_page.embedded_workshop_settings_desc', { defaultValue: '默认收起。展开后可微调校对设置，并可改成和翻译模型不同的组合。' }),
                action: (
                  <Switch
                    label={t('translation_page.embedded_workshop_enabled', { defaultValue: '在翻译工作流中嵌入智能工坊格式校对' })}
                    description={t('translation_page.embedded_workshop_enabled_desc', { defaultValue: '默认开启。翻译完成后会自动执行一轮格式问题修复，再生成最新的校验结果。' })}
                    checked={form.values.embedded_workshop_enabled}
                    onChange={(event) => form.setFieldValue('embedded_workshop_enabled', event.currentTarget.checked)}
                  />
                ),
                disabled: !form.values.embedded_workshop_enabled,
                children: (
                  <Stack gap="sm">
                    <Alert variant="light" color="blue" radius="md">
                      <Text size="sm">
                        {form.values.embedded_workshop_follow_primary_settings
                          ? t('translation_page.embedded_workshop_following_summary', {
                            defaultValue: '当前将跟随主翻译配置：{{provider}} / {{model}}',
                            provider: form.values.api_provider || '--',
                            model: form.values.model_name || '--',
                          })
                          : t('translation_page.embedded_workshop_custom_summary', {
                            defaultValue: '当前使用独立校对配置：{{provider}} / {{model}}',
                            provider: form.values.embedded_workshop_api_provider || '--',
                            model: form.values.embedded_workshop_api_model || '--',
                          })}
                      </Text>
                    </Alert>

                    <Switch
                      label={t('translation_page.embedded_workshop_follow', { defaultValue: '默认跟随当前翻译 API 与模型' })}
                      description={t('translation_page.embedded_workshop_follow_desc', { defaultValue: '关闭后可单独指定校对模型，例如大模型翻译、小模型校对。' })}
                      checked={form.values.embedded_workshop_follow_primary_settings}
                      onChange={(event) => {
                        const checked = event.currentTarget.checked;
                        form.setFieldValue('embedded_workshop_follow_primary_settings', checked);
                        if (!checked && !form.values.embedded_workshop_api_provider) {
                          form.setFieldValue('embedded_workshop_api_provider', form.values.api_provider);
                          form.setFieldValue('embedded_workshop_api_model', form.values.model_name || '');
                        }
                      }}
                    />

                    {!form.values.embedded_workshop_follow_primary_settings && (
                      <Group grow align="flex-start">
                        <Box style={{ flex: 1 }}>
                          {renderNativeSelect({
                            label: t('translation_page.embedded_workshop_provider', { defaultValue: '校对 API' }),
                            value: form.values.embedded_workshop_api_provider,
                            options: providerOptions,
                            onChange: (event) => {
                              const providerValue = event.currentTarget.value;
                              const models = buildModelOptions(providerValue, config.api_providers);
                              form.setFieldValue('embedded_workshop_api_provider', providerValue);
                              form.setFieldValue('embedded_workshop_api_model', models[0]?.value || '');
                            },
                          })}
                        </Box>
                        <Box style={{ flex: 1 }}>
                          {renderNativeSelect({
                            label: t('translation_page.embedded_workshop_model', { defaultValue: '校对模型' }),
                            value: form.values.embedded_workshop_api_model,
                            options: embeddedWorkshopModelOptions,
                            onChange: (event) => form.setFieldValue('embedded_workshop_api_model', event.currentTarget.value),
                          })}
                        </Box>
                      </Group>
                    )}

                    <Group grow align="flex-start">
                      <Box style={{ flex: 1 }}>
                        {renderNativeSelect({
                          label: t('translation_page.embedded_workshop_batch_size', { defaultValue: '每批修复条数' }),
                          value: form.values.embedded_workshop_batch_size_limit,
                          options: ['3', '5', '10', '15', '20'].map((value) => ({ value, label: value })),
                          onChange: (event) => form.setFieldValue('embedded_workshop_batch_size_limit', event.currentTarget.value),
                        })}
                      </Box>
                      <Box style={{ flex: 1 }}>
                        {renderNativeSelect({
                          label: t('translation_page.embedded_workshop_concurrency', { defaultValue: '校对并发' }),
                          value: form.values.embedded_workshop_concurrency_limit,
                          options: ['1', '2', '3', '5'].map((value) => ({ value, label: value })),
                          onChange: (event) => form.setFieldValue('embedded_workshop_concurrency_limit', event.currentTarget.value),
                        })}
                      </Box>
                      <Box style={{ flex: 1 }}>
                        {renderNativeSelect({
                          label: t('translation_page.embedded_workshop_rpm', { defaultValue: '校对 RPM' }),
                          value: form.values.embedded_workshop_rpm_limit,
                          options: ['5', '10', '20', '40', '60', '100'].map((value) => ({ value, label: value })),
                          onChange: (event) => form.setFieldValue('embedded_workshop_rpm_limit', event.currentTarget.value),
                        })}
                      </Box>
                    </Group>
                  </Stack>
                ),
              })}

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
          </Card>
        </Grid.Col>
      </Grid>

      <Group justify="flex-end" mt="xl">
        <Button onClick={onBack} leftSection={<IconArrowLeft size={14} />} variant="default">
          {t('button_back')}
        </Button>
        <Button id="translation-start-btn" type="submit" size="lg">{t('button_start_translation')}</Button>
      </Group>
    </form>
  );
}
