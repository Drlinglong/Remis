import React, { useMemo, useState } from 'react';
import {
  Alert, Badge, Button, Group, NumberInput, Select, Stack, Switch, Text, TextInput,
} from '@mantine/core';
import { IconFolder, IconPlayerPlay, IconScan } from '@tabler/icons-react';
import { open } from '@tauri-apps/plugin-dialog';
import {
  executeGuidedLocalizationWorkflow,
  planLocalizationWorkflow,
} from '../../services/copilotService';
import styles from './InlineLocalizationWorkflow.module.css';

const games = [
  { value: 'stellaris', label: 'Stellaris' },
  { value: 'hoi4', label: 'Hearts of Iron IV' },
  { value: 'vic3', label: 'Victoria 3' },
  { value: 'ck3', label: 'Crusader Kings III' },
  { value: 'eu4', label: 'Europa Universalis IV' },
];

const languages = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
];

export default function InlineLocalizationWorkflow({ initialArgs = {}, onStarted, onClose }) {
  const [folderPath, setFolderPath] = useState(initialArgs.folder_path || '');
  const [projectName, setProjectName] = useState(initialArgs.project_name || '');
  const [gameId, setGameId] = useState(initialArgs.game_id || 'vic3');
  const [sourceLanguage, setSourceLanguage] = useState(initialArgs.source_language || 'en');
  const [targetLanguage, setTargetLanguage] = useState(initialArgs.target_language || 'zh-CN');
  const [provider, setProvider] = useState('lm_studio');
  const [model, setModel] = useState('google/gemma-4-31b-qat');
  const [batchSize, setBatchSize] = useState(10);
  const [concurrency, setConcurrency] = useState(1);
  const [rpm, setRpm] = useState(40);
  const [useResume, setUseResume] = useState(true);
  const [useMainGlossary, setUseMainGlossary] = useState(true);
  const [workshopEnabled, setWorkshopEnabled] = useState(true);
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const inferredName = useMemo(() => {
    const normalized = folderPath.replace(/[\\/]+$/, '');
    return normalized.split(/[\\/]/).pop() || 'New Mod';
  }, [folderPath]);

  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected === 'string') {
      setFolderPath(selected);
      if (!projectName) {
        const normalized = selected.replace(/[\\/]+$/, '');
        setProjectName(normalized.split(/[\\/]/).pop() || 'New Mod');
      }
    }
  };

  const buildPlan = async () => {
    setBusy(true);
    setError('');
    try {
      setPlan(await planLocalizationWorkflow({
        folder_path: folderPath,
        project_name: projectName || inferredName,
        game_id: gameId,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        import_mode: 'copy',
        api_provider: provider,
        model,
        batch_size_limit: batchSize,
        concurrency_limit: concurrency,
        rpm_limit: rpm,
        use_resume: useResume,
        use_main_glossary: useMainGlossary,
        embedded_workshop_enabled: workshopEnabled,
      }));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await executeGuidedLocalizationWorkflow(plan.plan_id);
      onStarted({
        taskId: result.task_id,
        projectId: result.project?.project_id,
        projectName: result.project?.name || projectName || inferredName,
        gameId,
        sourceLanguage,
        targetLanguage,
        provider,
        model,
        batchSize,
        concurrency,
        rpm,
        useResume,
        useMainGlossary,
        workshopEnabled,
        startedAt: new Date().toISOString(),
      });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.card}>
      <Stack gap="sm">
        <div>
          <Text fw={700}>在对话中规划汉化</Text>
          <Text size="sm" c="dimmed">我会先只读检查，再把所有写入和 API 参数交给你批准。</Text>
        </div>

        {!plan ? (
          <>
            <Alert color="blue" icon={<IconScan size={18} />}>当前阶段不会写文件、创建项目或调用翻译 API。</Alert>
            <Group align="flex-end" wrap="nowrap">
              <TextInput label="Mod 路径" value={folderPath} onChange={(e) => setFolderPath(e.currentTarget.value)} className={styles.grow} />
              <Button variant="default" leftSection={<IconFolder size={16} />} onClick={browse}>浏览</Button>
            </Group>
            <Group grow>
              <TextInput label="项目名称" value={projectName} placeholder={inferredName} onChange={(e) => setProjectName(e.currentTarget.value)} />
              <Select label="游戏" data={games} value={gameId} onChange={setGameId} />
            </Group>
            <Group grow>
              <Select label="源语言" data={languages} value={sourceLanguage} onChange={setSourceLanguage} />
              <Select label="目标语言" data={languages} value={targetLanguage} onChange={setTargetLanguage} />
            </Group>
            <Group grow>
              <Select label="Provider" data={[{ value: 'lm_studio', label: 'LM Studio' }, { value: 'ollama', label: 'Ollama' }, { value: 'openai', label: 'OpenAI' }, { value: 'gemini', label: 'Google Gemini' }]} value={provider} onChange={setProvider} />
              <TextInput label="模型" value={model} onChange={(e) => setModel(e.currentTarget.value)} />
            </Group>
            <Group grow>
              <NumberInput label="Batch" min={1} value={batchSize} onChange={setBatchSize} />
              <NumberInput label="并发" min={1} value={concurrency} onChange={setConcurrency} />
              <NumberInput label="RPM" min={1} value={rpm} onChange={setRpm} />
            </Group>
            <Group gap="lg">
              <Switch checked={useResume} onChange={(e) => setUseResume(e.currentTarget.checked)} label="断点续传" />
              <Switch checked={useMainGlossary} onChange={(e) => setUseMainGlossary(e.currentTarget.checked)} label="主词典" />
              <Switch checked={workshopEnabled} onChange={(e) => setWorkshopEnabled(e.currentTarget.checked)} label="智能工坊" />
            </Group>
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>取消</Button>
              <Button loading={busy} disabled={!folderPath || !model || sourceLanguage === targetLanguage} onClick={buildPlan}>只读检查并预览</Button>
            </Group>
          </>
        ) : (
          <>
            <Alert color="yellow" title={plan.title}>{plan.summary}</Alert>
            <Group gap="xs">
              <Badge color="teal">只读扫描完成</Badge>
              <Badge variant="outline">本地化文件 {plan.inspection?.localization_file_count ?? 0}</Badge>
              <Badge variant="outline">{sourceLanguage} → {targetLanguage}</Badge>
              <Badge variant="outline">{provider}</Badge>
            </Group>
            <div className={styles.parameters}>
              <Text size="sm"><b>路径：</b>{plan.inspection?.folder_path}</Text>
              <Text size="sm"><b>模型：</b>{model}</Text>
              <Text size="sm"><b>限流：</b>Batch {batchSize}，并发 {concurrency}，RPM {rpm}</Text>
              <Text size="sm"><b>增强：</b>{[useResume && '断点续传', useMainGlossary && '主词典', workshopEnabled && '智能工坊'].filter(Boolean).join('、') || '无'}</Text>
            </div>
            <Alert color="orange">批准后会创建 Remis 项目、复制受支持内容并立即启动后台翻译。源 Mod 不会被直接修改，在线 API 可能产生费用。</Alert>
            <Group justify="space-between">
              <Button variant="default" disabled={busy} onClick={() => setPlan(null)}>返回修改</Button>
              <Button color="green" leftSection={<IconPlayerPlay size={16} />} loading={busy} onClick={approve}>批准并启动翻译</Button>
            </Group>
          </>
        )}
        {error && <Alert color="red">{error}</Alert>}
      </Stack>
    </div>
  );
}
