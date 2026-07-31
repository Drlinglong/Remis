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

import { DescriptionGenerationSettings } from './DescriptionGenerationSettings';
import { useDescriptionModelConfig } from './useDescriptionModelConfig';

const DEFAULT_TEMPLATE = `[h1]本地化标题[/h1]

[b]请保留原作者信息，并为目标语言用户整理清晰的功能介绍、兼容性和使用说明。[/b]`;

export function DescriptionGenerationPanel({
  isGenerating,
  onGenerate,
  workshopItemId,
}) {
  const [opened, setOpened] = useState(false);
  const [approved, setApproved] = useState(false);
  const [language, setLanguage] = useState('zh-CN');
  const [userTemplate, setUserTemplate] = useState(DEFAULT_TEMPLATE);
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
          <Text fw={700}>从现有工坊描述生成候选版本</Text>
          <Text c="dimmed" size="sm">
            {workshopItemId
              ? `将读取 Workshop ID ${workshopItemId}，调用所选模型并保存为候选版本。`
              : '先在发布工作区中绑定 Workshop ID，才能读取现有描述。'}
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
          模型生成
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
        title="确认模型生成"
        size="lg"
      >
        <Stack data-remis-surface="elevated">
          <Alert color="yellow" title="本次调用摘要">
            <Stack gap="xs">
              <Text size="sm"><strong>Workshop ID：</strong>{workshopItemId}</Text>
              <Text size="sm"><strong>API 供应商：</strong>{selectedProvider?.label || provider || '未选择'}</Text>
              <Text size="sm"><strong>模型：</strong>{model || '未选择'}</Text>
              <Text size="sm"><strong>描述语言：</strong>{selectedLanguage?.label || '未选择'}</Text>
              <Text size="sm" c="dimmed">
                Remis 将读取公开的 Steam 工坊描述，并把模板和源描述发送给所选模型。
                结果只保存为候选版本，不会自动采用或上传 Steam。
              </Text>
            </Stack>
          </Alert>
          <Checkbox
            checked={approved}
            onChange={(event) => setApproved(event.currentTarget.checked)}
            label="我确认执行这次模型调用，并将结果保存为候选版本"
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeModal}>取消</Button>
            <Button
              loading={isGenerating}
              disabled={!approved || !canGenerate}
              onClick={handleGenerate}
            >
              确认生成
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Paper>
  );
}
