import React from 'react';
import { Alert, Code, Select, Stack, Switch, Text, Textarea } from '@mantine/core';
import { IconBrain, IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

const PRESET_LABEL_KEYS = {
  low: 'api_reasoning_preset_low',
  medium: 'api_reasoning_preset_medium',
  high: 'api_reasoning_preset_high',
  xhigh: 'api_reasoning_preset_xhigh',
  max: 'api_reasoning_preset_max',
};

const ProviderReasoningSettings = ({ reasoning, form, onChange }) => {
  const { t } = useTranslation();
  const supported = Boolean(reasoning?.supported);
  const presets = reasoning?.available_presets || [];

  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>{t('api_reasoning_title')}</Text>
      <Text size="xs" c="dimmed">{t('api_reasoning_description')}</Text>

      {!supported && (
        <Alert color="yellow" variant="light" icon={<IconInfoCircle size={16} />}>
          {t('api_reasoning_unverified')}
        </Alert>
      )}

      <Switch
        label={t('api_reasoning_builtin_label')}
        description={t('api_reasoning_builtin_description')}
        checked={form.reasoningBuiltinEnabled}
        disabled={!supported}
        onChange={(event) => onChange({ reasoningBuiltinEnabled: event.currentTarget.checked })}
        thumbIcon={<IconBrain size={12} />}
      />

      {supported && (
        <Select
          label={t('api_reasoning_preset_label')}
          description={t('api_reasoning_preset_description')}
          data={presets.map((preset) => ({
            value: preset,
            label: t(PRESET_LABEL_KEYS[preset] || preset),
          }))}
          value={form.reasoningPreset}
          disabled={!form.reasoningBuiltinEnabled}
          onChange={(value) => onChange({ reasoningPreset: value })}
          allowDeselect={false}
          size="xs"
        />
      )}

      {form.reasoningBuiltinEnabled && Object.keys(reasoning?.mapping_preview || {}).length > 0 && (
        <Code block>{JSON.stringify(reasoning.mapping_preview, null, 2)}</Code>
      )}

      <Textarea
        label={t('api_custom_parameters_label')}
        description={t('api_custom_parameters_description')}
        placeholder={'{\n  "reasoning": {"effort": "low"}\n}'}
        value={form.customParametersText}
        onChange={(event) => onChange({ customParametersText: event.currentTarget.value })}
        autosize
        minRows={3}
        maxRows={10}
        size="xs"
      />
      <Text size="xs" c="dimmed">{t('api_custom_parameters_priority')}</Text>
    </Stack>
  );
};

export default ProviderReasoningSettings;
