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
  return (
    <>
      {isConfigLoading && (
        <Alert color="blue" title="正在读取 API 配置">
          正在读取供应商、模型和描述语言选项…
        </Alert>
      )}
      {loadError && (
        <Alert
          color="red"
          title="API 配置读取失败"
          withCloseButton={false}
        >
          <Group justify="space-between" align="center">
            <Text size="sm">{loadError}</Text>
            <Button variant="light" color="red" size="xs" onClick={loadConfig}>
              重试
            </Button>
          </Group>
        </Alert>
      )}
      {!isConfigLoading && !loadError && !hasProviders && (
        <Alert color="blue" title="尚未配置 API 供应商">
          请先前往设置中的 API 设置添加供应商和模型，再返回执行生成。
        </Alert>
      )}
      {!isConfigLoading && !loadError && hasProviders && provider && !hasModels && (
        <Alert color="blue" title="当前供应商没有可用模型">
          请在设置中的 API 设置为该供应商添加或选择模型。
        </Alert>
      )}
      {!isConfigLoading && !loadError && hasProviders && provider && hasModels && missingApiKey && (
        <Alert color="yellow" title="尚未配置 API 密钥">
          请先前往设置中的 API 设置保存该供应商的密钥，再执行模型生成。
        </Alert>
      )}
      {!isConfigLoading && !loadError && !hasLanguages && (
        <Alert color="blue" title="没有可用的描述语言">
          Remis 没有返回可用的语言配置，请检查服务后重试。
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Select
          label="API 供应商"
          placeholder={isConfigLoading ? '正在读取配置…' : '选择 API 供应商'}
          data={providerOptions}
          value={provider || null}
          title={provider || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !hasProviders}
          onChange={onProviderChange}
        />
        <Select
          label="模型"
          placeholder={
            isConfigLoading
              ? '正在读取配置…'
              : !hasProviders
                ? '请先配置 API 供应商'
                : hasModels
                  ? '选择模型'
                  : '当前供应商没有可用模型'
          }
          data={modelOptions}
          value={model || null}
          title={model || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !provider || !hasModels}
          onChange={onModelChange}
        />
        <Select
          label="描述语言"
          description="使用该语言来生成创意工坊描述"
          placeholder={isConfigLoading ? '正在读取配置…' : '选择描述语言'}
          data={languageOptions}
          value={language || null}
          title={selectedLanguage?.label || undefined}
          disabled={isConfigLoading || Boolean(loadError) || !hasLanguages}
          onChange={onLanguageChange}
        />
      </SimpleGrid>

      <Textarea
        label="发布模板"
        description="先在这里整理生成结果需要遵循的标题、结构和内容要求。"
        minRows={8}
        value={userTemplate}
        onChange={onTemplateChange}
      />
    </>
  );
}
