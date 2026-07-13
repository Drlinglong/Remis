import React, { useEffect, useState } from 'react';
import { Alert, Badge, Button, Group, Modal, NumberInput, SegmentedControl, Select, Stack, Switch, Text, TextInput } from '@mantine/core';
import { IconCheck, IconFolder, IconPlayerPlay, IconScan } from '@tabler/icons-react';
import { open } from '@tauri-apps/plugin-dialog';
import {
  executeCopilotWorkflow,
  executeInitialTranslationWorkflow,
  planInitialTranslationWorkflow,
  planLocalizationWorkflow,
  recommendInitialTranslationWorkflow,
} from '../../services/copilotService';

const games = [
  { value: 'stellaris', label: 'Stellaris' },
  { value: 'hoi4', label: 'Hearts of Iron IV' },
  { value: 'vic3', label: 'Victoria 3' },
  { value: 'ck3', label: 'Crusader Kings III' },
  { value: 'eu4', label: 'Europa Universalis IV' },
];

export default function LocalizationWorkflowModal({ opened, onClose, onNavigate }) {
  const [folderPath, setFolderPath] = useState('');
  const [projectName, setProjectName] = useState('');
  const [gameId, setGameId] = useState('stellaris');
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [importMode, setImportMode] = useState('copy');
  const [plan, setPlan] = useState(null);
  const [result, setResult] = useState(null);
  const [translationPlan, setTranslationPlan] = useState(null);
  const [translationResult, setTranslationResult] = useState(null);
  const [translationConfigOpen, setTranslationConfigOpen] = useState(false);
  const [targetLanguage, setTargetLanguage] = useState('zh-CN');
  const [provider, setProvider] = useState('lm_studio');
  const [model, setModel] = useState('google/gemma-4-31b-qat');
  const [batchSize, setBatchSize] = useState(10);
  const [concurrency, setConcurrency] = useState(1);
  const [rpm, setRpm] = useState(40);
  const [useResume, setUseResume] = useState(true);
  const [useMainGlossary, setUseMainGlossary] = useState(true);
  const [workshopEnabled, setWorkshopEnabled] = useState(true);
  const [recommendationNote, setRecommendationNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!opened) {
      setPlan(null);
      setResult(null);
      setTranslationPlan(null);
      setTranslationResult(null);
      setTranslationConfigOpen(false);
      setError('');
    }
  }, [opened]);

  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected === 'string') {
      setFolderPath(selected);
      const normalized = selected.replace(/[\\/]+$/, '');
      setProjectName(normalized.split(/[\\/]/).pop() || 'New Mod');
    }
  };

  const buildPlan = async () => {
    setBusy(true);
    setError('');
    try {
      setPlan(await planLocalizationWorkflow({
        folder_path: folderPath,
        project_name: projectName,
        game_id: gameId,
        source_language: sourceLanguage,
        import_mode: importMode,
      }));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const execute = async () => {
    setBusy(true);
    setError('');
    try {
      setResult(await executeCopilotWorkflow(plan.plan_id));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const buildTranslationPlan = async () => {
    setBusy(true);
    setError('');
    try {
      setTranslationPlan(await planInitialTranslationWorkflow({
        project_id: result.project?.project_id,
        target_lang_codes: [targetLanguage],
        api_provider: provider,
        model,
        batch_size_limit: batchSize,
        concurrency_limit: concurrency,
        rpm_limit: rpm,
        use_resume: useResume,
        use_main_glossary: useMainGlossary,
        embedded_workshop_enabled: workshopEnabled,
      }));
      setTranslationConfigOpen(false);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const askAgentForRecommendation = async () => {
    setBusy(true);
    setError('');
    try {
      const data = await recommendInitialTranslationWorkflow({
        project_id: result.project?.project_id,
        target_lang_codes: [targetLanguage],
        preferred_provider: provider,
        planner_provider: 'lm_studio',
        planner_model: 'google/gemma-4-31b-qat',
      });
      const rec = data.recommendation || {};
      if (rec.api_provider) setProvider(rec.api_provider);
      if (rec.model) setModel(rec.model);
      if (rec.batch_size_limit) setBatchSize(rec.batch_size_limit);
      if (rec.concurrency_limit) setConcurrency(rec.concurrency_limit);
      if (rec.rpm_limit) setRpm(rec.rpm_limit);
      if (typeof rec.use_resume === 'boolean') setUseResume(rec.use_resume);
      if (typeof rec.use_main_glossary === 'boolean') setUseMainGlossary(rec.use_main_glossary);
      if (typeof rec.embedded_workshop_enabled === 'boolean') setWorkshopEnabled(rec.embedded_workshop_enabled);
      setRecommendationNote(`${rec.summary || 'Agent 已给出建议'}（读取工具：${(data.tool_calls || []).map((item) => item.name).join('、')}）`);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const executeTranslation = async () => {
    setBusy(true);
    setError('');
    try {
      setTranslationResult(await executeInitialTranslationWorkflow(translationPlan.plan_id));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="汉化工作流" size="lg" closeOnClickOutside={!busy}>
      <Stack>
        {!plan && !result && (
          <>
            <Alert color="blue" icon={<IconScan size={18} />}>
              选择文件夹后，Agent 只读取目录结构和文件名来制定计划。此阶段不会写入文件或数据库。
            </Alert>
            <Group align="flex-end">
              <TextInput label="Mod 文件夹" value={folderPath} onChange={(event) => setFolderPath(event.currentTarget.value)} style={{ flex: 1 }} />
              <Button leftSection={<IconFolder size={16} />} onClick={browse}>浏览</Button>
            </Group>
            <TextInput label="项目名称" value={projectName} onChange={(event) => setProjectName(event.currentTarget.value)} />
            <Select label="游戏" data={games} value={gameId} onChange={setGameId} />
            <Select label="源语言" data={[{ value: 'en', label: 'English' }, { value: 'zh-CN', label: '简体中文' }]} value={sourceLanguage} onChange={setSourceLanguage} />
            <SegmentedControl value={importMode} onChange={setImportMode} data={[{ value: 'copy', label: '复制到 Remis 工作区' }, { value: 'reference', label: '引用原目录' }]} />
            <Button loading={busy} disabled={!folderPath || !projectName} onClick={buildPlan}>只读检查并生成计划</Button>
          </>
        )}

        {plan && !result && (
          <>
            <Alert color="yellow" title={plan.title}>{plan.summary}</Alert>
            <Group gap="xs">
              <Badge color="teal">只读扫描完成</Badge>
              <Badge variant="outline">本地化文件 {plan.inspection?.localization_file_count ?? 0}</Badge>
              <Badge variant="outline">已扫描 {plan.inspection?.total_files_scanned ?? 0} 个文件</Badge>
            </Group>
            <Stack gap="xs">
              {(plan.steps || []).map((step, index) => (
                <Group key={step.id} justify="space-between" wrap="nowrap">
                  <Text size="sm">{index + 1}. {step.label}</Text>
                  <Badge color={step.status === 'completed' ? 'green' : 'gray'}>{step.status}</Badge>
                </Group>
              ))}
            </Stack>
            <Alert color={importMode === 'copy' ? 'orange' : 'yellow'}>
              批准后将写入 Remis 项目数据库{importMode === 'copy' ? '，并把受支持的 Mod 内容复制到 Remis 工作区。' : '；引用模式不会复制源文件。'}不会立即启动 AI 翻译。
            </Alert>
            <Group justify="space-between">
              <Button variant="default" disabled={busy} onClick={() => setPlan(null)}>返回修改</Button>
              <Button color="green" leftSection={<IconPlayerPlay size={16} />} loading={busy} onClick={execute}>批准并执行</Button>
            </Group>
          </>
        )}

        {result && !translationConfigOpen && !translationPlan && !translationResult && (
          <>
            <Alert color="green" icon={<IconCheck size={18} />} title="工作流已完成">
              项目“{result.project?.name}”已经创建。翻译尚未启动，你可以继续配置初次翻译。
            </Alert>
            <Group grow>
              <Button variant="default" onClick={() => onNavigate(result.next_action)}>手动打开初次翻译</Button>
              <Button onClick={() => setTranslationConfigOpen(true)}>继续规划翻译</Button>
            </Group>
          </>
        )}
        {result && translationConfigOpen && !translationPlan && (
          <>
            <Alert color="blue">Agent 已只读取得项目信息。请确认翻译参数，下一页仍会要求第二次批准。</Alert>
            <Select label="目标语言" data={[{ value: 'zh-CN', label: '简体中文' }, { value: 'en', label: 'English' }, { value: 'ja', label: '日本語' }, { value: 'ko', label: '한국어' }]} value={targetLanguage} onChange={setTargetLanguage} />
            <Select label="Provider" data={[{ value: 'lm_studio', label: 'LM Studio' }, { value: 'ollama', label: 'Ollama' }, { value: 'openai', label: 'OpenAI' }, { value: 'gemini', label: 'Google Gemini' }]} value={provider} onChange={setProvider} />
            <TextInput label="模型" value={model} onChange={(event) => setModel(event.currentTarget.value)} />
            <Group grow>
              <NumberInput label="Batch" min={1} value={batchSize} onChange={setBatchSize} />
              <NumberInput label="并发" min={1} value={concurrency} onChange={setConcurrency} />
              <NumberInput label="RPM" min={1} value={rpm} onChange={setRpm} />
            </Group>
            <Switch checked={useResume} onChange={(event) => setUseResume(event.currentTarget.checked)} label="启用断点续传" />
            <Switch checked={useMainGlossary} onChange={(event) => setUseMainGlossary(event.currentTarget.checked)} label="使用主词典" />
            <Switch checked={workshopEnabled} onChange={(event) => setWorkshopEnabled(event.currentTarget.checked)} label="翻译后运行嵌入式智能工坊" />
            <Button variant="light" loading={busy} onClick={askAgentForRecommendation}>让 Agent 读取项目并推荐配置</Button>
            {recommendationNote && <Alert color="teal">{recommendationNote}</Alert>}
            <Group justify="space-between">
              <Button variant="default" onClick={() => setTranslationConfigOpen(false)}>返回</Button>
              <Button loading={busy} disabled={!model} onClick={buildTranslationPlan}>生成翻译计划</Button>
            </Group>
          </>
        )}
        {translationPlan && !translationResult && (
          <>
            <Alert color="orange" title={translationPlan.title}>{translationPlan.summary}</Alert>
            <Group gap="xs">
              <Badge variant="outline">文件 {translationPlan.inspection?.project_file_count ?? 0}</Badge>
              <Badge variant="outline">{provider}</Badge>
              <Badge variant="outline">{model}</Badge>
              <Badge color="violet">{targetLanguage}</Badge>
            </Group>
            {(translationPlan.steps || []).map((step, index) => (
              <Group key={step.id} justify="space-between">
                <Text size="sm">{index + 1}. {step.label}</Text>
                <Badge color={step.status === 'completed' ? 'green' : 'gray'}>{step.status}</Badge>
              </Group>
            ))}
            <Alert color="red">批准后会立即创建后台翻译任务并写入翻译输出。Agent 不会直接修改源 Mod，但 API 调用可能产生费用。</Alert>
            <Group justify="space-between">
              <Button variant="default" disabled={busy} onClick={() => { setTranslationPlan(null); setTranslationConfigOpen(true); }}>返回修改</Button>
              <Button color="green" loading={busy} onClick={executeTranslation}>批准并启动翻译</Button>
            </Group>
          </>
        )}
        {translationResult && (
          <>
            <Alert color="green" icon={<IconCheck size={18} />} title="翻译任务已启动">
              Task ID：{translationResult.task_id}。可进入初次翻译页面查看实时进度。
            </Alert>
            <Button onClick={() => onNavigate({ action: 'open_initial_translation', args: { task_id: translationResult.task_id, project_id: result.project?.project_id } })}>查看翻译进度</Button>
          </>
        )}
        {error && <Alert color="red">{error}</Alert>}
      </Stack>
    </Modal>
  );
}
