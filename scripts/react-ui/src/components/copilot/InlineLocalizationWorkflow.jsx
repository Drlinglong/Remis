import React from 'react';
import {
  Alert, Badge, Button, Group, MultiSelect, NumberInput, Select, Stack, Switch, Text, TextInput,
} from '@mantine/core';
import { IconFolder, IconPlayerPlay, IconScan } from '@tabler/icons-react';
import useInlineLocalizationWorkflow from './useInlineLocalizationWorkflow';
import styles from './InlineLocalizationWorkflow.module.css';

export default function InlineLocalizationWorkflow({
  initialArgs = {}, onStarted, onClose, onRecoveryAction,
}) {
  const workflow = useInlineLocalizationWorkflow({ initialArgs, onStarted, onRecoveryAction });
  const {
    approve, availableTargetLanguages, batchSize, browse, buildPlan, busy, changeProvider,
    concurrency, error, folderPath, gameLabel, inferredName, loadingSettings, model, modelOptions, plan,
    preparationError, projectName, provider, providerOptions, resolvedProject, resolvingProject, rpm,
    openRecoveredProject, partialSuccess, planInvalidation, regeneratePlan, resetPlan,
    setBatchSize, setConcurrency, setModel, setRpm, setTargetLanguages,
    setUseMainGlossary, setUseResume, setWorkshopEnabled, sourceLanguage,
    sourceLanguageLabel, targetLanguages, useMainGlossary, useResume, workshopEnabled,
  } = workflow;

  if (resolvingProject || loadingSettings) {
    return (
      <div className={styles.card} role="status" aria-live="polite">
        <Text fw={700}>正在准备汉化计划</Text>
        <Text size="sm" c="dimmed">正在读取已有项目和小助手设置，确认完成后才会显示审批参数。</Text>
      </div>
    );
  }

  if (preparationError) {
    return (
      <div className={styles.card}>
        <Stack gap="sm">
          <Alert color="red" title="无法准备汉化计划">{preparationError}</Alert>
          <Group justify="flex-end"><Button variant="default" onClick={onClose}>关闭</Button></Group>
        </Stack>
      </div>
    );
  }

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
              <TextInput label="Mod 路径" value={folderPath} readOnly variant="filled" className={styles.grow} />
              {!resolvedProject && <Button variant="default" leftSection={<IconFolder size={16} />} onClick={browse}>浏览</Button>}
            </Group>
            <Group grow>
              <TextInput label="项目名称" value={projectName || inferredName} readOnly variant="filled" />
              <TextInput label="游戏" value={gameLabel} readOnly variant="filled" />
            </Group>
            <Group grow>
              <TextInput label="源语言" value={sourceLanguageLabel} readOnly variant="filled" />
              {resolvedProject ? (
                <MultiSelect
                  label="目标语言"
                  data={availableTargetLanguages}
                  value={targetLanguages}
                  onChange={setTargetLanguages}
                  searchable
                  clearable
                />
              ) : (
                <Select
                  label="目标语言"
                  data={availableTargetLanguages}
                  value={targetLanguages[0] || null}
                  onChange={(value) => setTargetLanguages(value ? [value] : [])}
                  allowDeselect={false}
                />
              )}
            </Group>
            {resolvedProject && targetLanguages.length === 0 && (
              <Alert color="yellow">
                该项目记录的源语言是 {sourceLanguageLabel}，不能同时作为目标语言。请改选目标语言，或先在项目管理中修正项目元数据。
              </Alert>
            )}
            <Group grow>
              <Select label="Provider" data={providerOptions} value={provider} onChange={changeProvider} />
              {modelOptions.length ? (
                <Select label="模型" searchable data={modelOptions} value={model} onChange={setModel} />
              ) : (
                <TextInput label="模型" value={model} onChange={(e) => setModel(e.currentTarget.value)} />
              )}
            </Group>
            <Text size="xs" c="dimmed">默认值来自“设置 → 小助手设置”；本次翻译仍可在批准前修改。</Text>
            <Group grow>
              <NumberInput label="Batch" min={1} value={batchSize} onChange={setBatchSize} />
              <NumberInput label="并发" min={1} value={concurrency} onChange={setConcurrency} />
              <NumberInput label="RPM" min={1} value={rpm} onChange={setRpm} />
            </Group>
            <Group gap="lg">
              <Switch checked={useResume} onChange={(e) => setUseResume(e.currentTarget.checked)} label="断点续传" />
              <Switch checked={useMainGlossary} onChange={(e) => setUseMainGlossary(e.currentTarget.checked)} label="主词典" />
              <Switch checked={workshopEnabled} onChange={(e) => setWorkshopEnabled(e.currentTarget.checked)} label="格式修复台" />
            </Group>
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>取消</Button>
              <Button loading={busy || resolvingProject} disabled={!folderPath || !model || targetLanguages.length === 0} onClick={buildPlan}>只读检查并预览</Button>
            </Group>
          </>
        ) : (
          <>
            <Alert color="yellow" title={plan.title}>{plan.summary}</Alert>
            {planInvalidation && (
              <Alert
                color="red"
                title="预览已失效，不能批准"
                data-copilot-approval-invalid="true"
                data-copilot-approval-error-code={planInvalidation.code || undefined}
              >
                {planInvalidation.code?.includes('expired')
                  ? '批准窗口已过期，请重新执行只读检查。'
                  : planInvalidation.code?.includes('stale')
                    ? '项目或扫描状态已经变化，请重新执行只读检查。'
                    : planInvalidation.code?.includes('restart') || planInvalidation.code?.includes('not_found')
                      ? 'Remis 已重启或旧预览已不存在，请重新执行只读检查。'
                      : '该预览已不能安全批准，请重新执行只读检查。'}
              </Alert>
            )}
            {partialSuccess && (
              <Alert color="orange" title="项目已创建，但翻译尚未启动">
                Remis 已保留项目 {partialSuccess.project?.name || partialSuccess.project?.project_id}。
                本次没有产生翻译 task ID；请基于这个已有项目重新检查翻译参数，避免创建重复项目。
              </Alert>
            )}
            <Group gap="xs">
              <Badge color="teal">只读扫描完成</Badge>
              <Badge variant="outline">
                文件 {plan.inspection?.localization_file_count ?? plan.inspection?.project_file_count ?? 0}
              </Badge>
              <Badge variant="outline">{sourceLanguage} → {targetLanguages.join('、')}</Badge>
              <Badge variant="outline">{provider}</Badge>
            </Group>
            <div className={styles.parameters}>
              <Text size="sm"><b>路径：</b>{plan.inspection?.folder_path || plan.inspection?.source_path}</Text>
              <Text size="sm"><b>模型：</b>{model}</Text>
              <Text size="sm"><b>限流：</b>Batch {batchSize}，并发 {concurrency}，RPM {rpm}</Text>
              <Text size="sm"><b>增强：</b>{[useResume && '断点续传', useMainGlossary && '主词典', workshopEnabled && '格式修复台'].filter(Boolean).join('、') || '无'}</Text>
            </div>
            <Alert color={planInvalidation ? 'red' : 'orange'}>
              {partialSuccess
                ? '项目创建已经发生，但翻译任务尚未启动。恢复操作只会使用已创建的项目，不会重建同名项目。'
                : planInvalidation
                ? '这份风险说明属于旧预览；重新只读检查后，才能再次确认当前参数。'
                : '批准后会创建 Remis 项目、复制受支持内容并立即启动后台翻译。源 Mod 不会被直接修改，在线 API 可能产生费用。'}
            </Alert>
            <Group justify="space-between">
              <Button variant="default" disabled={busy} onClick={resetPlan}>返回修改</Button>
              <Group gap="xs">
                <Button
                  color="green"
                  leftSection={<IconPlayerPlay size={16} />}
                  loading={busy}
                  disabled={busy || Boolean(planInvalidation) || Boolean(partialSuccess)}
                  onClick={approve}
                >
                  批准并启动翻译
                </Button>
                {planInvalidation && (
                  <Button color="blue" loading={busy} disabled={busy} onClick={regeneratePlan}>
                    重新检查并生成预览
                  </Button>
                )}
                {partialSuccess && (
                  <>
                    <Button color="blue" loading={busy} disabled={busy} onClick={regeneratePlan}>
                      重新检查翻译参数
                    </Button>
                    <Button variant="default" disabled={busy} onClick={openRecoveredProject}>
                      打开已有项目
                    </Button>
                  </>
                )}
              </Group>
            </Group>
          </>
        )}
        {error && <Alert color="red">{error}</Alert>}
      </Stack>
    </div>
  );
}
