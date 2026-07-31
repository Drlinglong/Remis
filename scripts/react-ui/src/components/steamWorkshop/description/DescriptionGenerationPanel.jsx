import React, { useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  Paper,
  Stack,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core';
import { IconSparkles } from '@tabler/icons-react';

const DEFAULT_TEMPLATE = `[h1]本地化标题[/h1]

[b]请保留原作者信息，并为目标语言用户整理清晰的功能介绍、兼容性和使用说明。[/b]`;

export function DescriptionGenerationPanel({
  isGenerating,
  onGenerate,
  workshopItemId,
}) {
  const [opened, setOpened] = useState(false);
  const [approved, setApproved] = useState(false);
  const [provider, setProvider] = useState('lm_studio');
  const [model, setModel] = useState('');
  const [language, setLanguage] = useState('zh-CN');
  const [targetLanguageName, setTargetLanguageName] = useState('简体中文');
  const [userTemplate, setUserTemplate] = useState(DEFAULT_TEMPLATE);

  const handleGenerate = async () => {
    const created = await onGenerate({
      approved,
      language,
      model: model.trim(),
      provider: provider.trim(),
      target_language_name: targetLanguageName.trim(),
      user_template: userTemplate,
    });
    if (created) {
      setOpened(false);
      setApproved(false);
    }
  };

  const canGenerate = Boolean(
    workshopItemId
    && provider.trim()
    && model.trim()
    && targetLanguageName.trim(),
  );

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
          disabled={!workshopItemId}
          onClick={() => setOpened(true)}
        >
          模型生成
        </Button>
      </Group>

      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title="确认模型生成"
        size="lg"
      >
        <Stack data-remis-surface="elevated">
          <Alert color="yellow" title="这会调用模型">
            Remis 将读取公开的 Steam 工坊描述，并把模板和源描述发送给你选择的模型。
            生成结果只保存为候选版本，不会自动采用或上传 Steam。
          </Alert>
          <Group grow>
            <TextInput label="Provider" value={provider} onChange={(event) => setProvider(event.currentTarget.value)} />
            <TextInput label="Model" value={model} onChange={(event) => setModel(event.currentTarget.value)} />
          </Group>
          <Group grow>
            <TextInput label="语言代码" value={language} onChange={(event) => setLanguage(event.currentTarget.value)} />
            <TextInput label="目标语言" value={targetLanguageName} onChange={(event) => setTargetLanguageName(event.currentTarget.value)} />
          </Group>
          <Textarea
            label="发布模板"
            minRows={8}
            value={userTemplate}
            onChange={(event) => setUserTemplate(event.currentTarget.value)}
          />
          <Checkbox
            checked={approved}
            onChange={(event) => setApproved(event.currentTarget.checked)}
            label="我确认执行这次模型调用，并将结果保存为候选版本"
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpened(false)}>取消</Button>
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
