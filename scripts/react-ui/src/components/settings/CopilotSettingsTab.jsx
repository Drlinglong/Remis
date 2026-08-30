import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Group, Loader, Paper, Select, Stack, Switch, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBrain, IconRobot } from '@tabler/icons-react';
import { fetchCopilotSettings, saveCopilotSettings } from '../../services/copilotService';
import { applyReasoningToggle } from './copilotSettingsForm';

const presetLabels = {
  minimal: '最少',
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '极高',
  max: '最大',
};

export default function CopilotSettingsTab() {
  const [providers, setProviders] = useState([]);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCopilotSettings()
      .then((data) => {
        setProviders(data.providers || []);
        setForm(data.settings);
      })
      .catch((error) => notifications.show({
        title: '无法读取小助手设置',
        message: error?.response?.data?.detail || error.message,
        color: 'red',
      }))
      .finally(() => setLoading(false));
  }, []);

  const selectedProvider = useMemo(
    () => providers.find((item) => item.id === form?.provider),
    [form?.provider, providers],
  );
  const reasoningModel = selectedProvider?.reasoning_models?.[form?.model];
  const presets = Object.keys(reasoningModel?.presets || {});

  if (loading || !form) return <Loader size="sm" />;

  const changeProvider = (providerId) => {
    const provider = providers.find((item) => item.id === providerId);
    const model = provider?.default_model || provider?.models?.[0] || '';
    const nextPresets = Object.keys(provider?.reasoning_models?.[model]?.presets || {});
    setForm((current) => ({
      ...current,
      provider: providerId,
      model,
      reasoning_enabled: false,
      reasoning_preset: nextPresets.includes(current.reasoning_preset)
        ? current.reasoning_preset
        : nextPresets[0] || 'medium',
    }));
  };

  const changeModel = (model) => {
    const nextPresets = Object.keys(selectedProvider?.reasoning_models?.[model]?.presets || {});
    setForm((current) => ({
      ...current,
      model,
      reasoning_enabled: false,
      reasoning_preset: nextPresets.includes(current.reasoning_preset)
        ? current.reasoning_preset
        : nextPresets[0] || 'medium',
    }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const saved = await saveCopilotSettings({
        provider: form.provider,
        model: form.model,
        reasoning_enabled: form.reasoning_enabled,
        reasoning_preset: form.reasoning_preset,
      });
      setForm(saved);
      notifications.show({ title: '已保存', message: '所有 Remis 小助手入口将使用这套设置。', color: 'green' });
    } catch (error) {
      notifications.show({
        title: '保存失败',
        message: error?.response?.data?.detail || error.message,
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  };

  const changeReasoningEnabled = (event) => {
    applyReasoningToggle(event, setForm, presets);
  };

  return (
    <Stack gap="lg">
      <div>
        <Group gap="xs"><IconRobot size={22} /><Title order={3}>小助手设置</Title></Group>
        <Text size="sm" c="dimmed" mt={4}>
          统一控制独立小助手、右下角气泡以及 Workflow Agent 规划时使用的模型。
        </Text>
        <Text size="sm" c="dimmed" mt={4}>
          当前生效上下文输入预算：{form?.context_budget_tokens || 200000} tokens。Remis 会优先丢弃较早消息并保留最后一条用户消息；没有可靠的供应商/模型上限时，超限会显示可恢复提示。
        </Text>
      </div>
      <Alert color="blue">
        API Key 仍只在“API 设置”中管理。本页不会显示、复制或记录任何密钥。
      </Alert>
      <Paper withBorder p="md" radius="md">
        <Stack>
          <Select
            label="供应商"
            data={providers.map((item) => ({ value: item.id, label: item.name }))}
            value={form.provider}
            onChange={changeProvider}
            allowDeselect={false}
          />
          <Select
            label="模型"
            searchable
            data={(selectedProvider?.models || []).map((model) => ({ value: model, label: model }))}
            value={form.model}
            onChange={changeModel}
            allowDeselect={false}
          />
          <Switch
            label="启用模型内置推理"
            description={reasoningModel ? '只发送 Remis 已验证的该模型参数。' : '该模型没有已验证的推理参数映射。'}
            checked={form.reasoning_enabled}
            disabled={!reasoningModel}
            onChange={changeReasoningEnabled}
            thumbIcon={<IconBrain size={12} />}
          />
          <Select
            label="推理强度"
            data={presets.map((preset) => ({ value: preset, label: presetLabels[preset] || preset }))}
            value={presets.includes(form.reasoning_preset) ? form.reasoning_preset : presets[0] || null}
            disabled={!form.reasoning_enabled}
            onChange={(reasoningPreset) => setForm((current) => ({ ...current, reasoning_preset: reasoningPreset }))}
            allowDeselect={false}
          />
          <Group justify="flex-end">
            <Button loading={saving} disabled={!form.model} onClick={save}>保存小助手设置</Button>
          </Group>
        </Stack>
      </Paper>
    </Stack>
  );
}
