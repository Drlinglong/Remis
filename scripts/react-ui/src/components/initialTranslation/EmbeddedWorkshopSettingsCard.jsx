import React from 'react';
import { Alert, Box, Group, Stack, Switch, Text } from '@mantine/core';
import { IconRobot } from '@tabler/icons-react';

import { buildModelOptions } from '../../utils/initialTranslation';
import CollapsibleSettingsCard from './CollapsibleSettingsCard';

export default function EmbeddedWorkshopSettingsCard({
  config,
  embeddedWorkshopModelOptions,
  form,
  providerOptions,
  renderInfoLabel,
  renderNativeSelect,
  t,
}) {
  const [showWorkshopSettings, setShowWorkshopSettings] = React.useState(false);

  return (
    <CollapsibleSettingsCard
      accent="blue"
      icon={<IconRobot size={18} />}
      isOpen={showWorkshopSettings}
      onToggle={() => setShowWorkshopSettings((value) => !value)}
      t={t}
      title={t('translation_page.embedded_workshop_settings', { defaultValue: '智能工坊设置' })}
      description={t('translation_page.embedded_workshop_settings_desc', { defaultValue: '默认收起。展开后可微调校对设置，并可改成和翻译模型不同的组合。' })}
      action={(
        <Switch
          id="embedded-workshop-switch"
          label={t('translation_page.embedded_workshop_enabled', { defaultValue: '在翻译工作流中嵌入智能工坊格式校对' })}
          description={t('translation_page.embedded_workshop_enabled_desc', { defaultValue: '默认开启。翻译完成后会自动执行一轮格式问题修复，再生成最新的校验结果。' })}
          checked={form.values.embedded_workshop_enabled}
          onChange={(event) => form.setFieldValue('embedded_workshop_enabled', event.currentTarget.checked)}
        />
      )}
      disabled={!form.values.embedded_workshop_enabled}
    >
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
          <>
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

            <Group grow align="flex-start">
              <Box style={{ flex: 1 }}>
                {renderNativeSelect({
                  label: renderInfoLabel(
                    t('translation_page.embedded_workshop_batch_size', { defaultValue: '每批修复条数' }),
                    t('translation_page.embedded_workshop_batch_size_tooltip', { defaultValue: '控制每次交给智能工坊修复的条目数量。只对本次翻译生效。' }),
                  ),
                  value: form.values.embedded_workshop_batch_size_limit,
                  options: ['3', '5', '10', '15', '20'].map((value) => ({ value, label: value })),
                  onChange: (event) => form.setFieldValue('embedded_workshop_batch_size_limit', event.currentTarget.value),
                })}
              </Box>
              <Box style={{ flex: 1 }}>
                {renderNativeSelect({
                  label: renderInfoLabel(
                    t('translation_page.embedded_workshop_concurrency', { defaultValue: '校对并发' }),
                    t('translation_page.embedded_workshop_concurrency_tooltip', { defaultValue: '控制智能工坊同时修复多少个批次。只对本次翻译生效。' }),
                  ),
                  value: form.values.embedded_workshop_concurrency_limit,
                  options: ['1', '2', '3', '5'].map((value) => ({ value, label: value })),
                  onChange: (event) => form.setFieldValue('embedded_workshop_concurrency_limit', event.currentTarget.value),
                })}
              </Box>
              <Box style={{ flex: 1 }}>
                {renderNativeSelect({
                  label: renderInfoLabel(
                    t('translation_page.embedded_workshop_rpm', { defaultValue: '校对 RPM' }),
                    t('translation_page.embedded_workshop_rpm_tooltip', { defaultValue: '限制智能工坊每分钟请求数。只对本次翻译生效。' }),
                  ),
                  value: form.values.embedded_workshop_rpm_limit,
                  options: ['5', '10', '20', '40', '60', '100'].map((value) => ({ value, label: value })),
                  onChange: (event) => form.setFieldValue('embedded_workshop_rpm_limit', event.currentTarget.value),
                })}
              </Box>
            </Group>
          </>
        )}
      </Stack>
    </CollapsibleSettingsCard>
  );
}
