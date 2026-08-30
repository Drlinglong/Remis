import { useCallback, useEffect, useMemo, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';

import {
  executeGuidedLocalizationWorkflow,
  executeInitialTranslationWorkflow,
  fetchCopilotSettings,
  planInitialTranslationWorkflow,
  planLocalizationWorkflow,
} from '../../services/copilotService';
import projectService from '../../services/projectService';
import { normalizeRecordArrayPayload } from '../../utils/payload';
import { getCopilotWorkflowError } from './copilotWorkflowErrors';
import { resolveCopilotProject } from './localizationWorkflowReadiness';

const GAMES = [
  { value: 'stellaris', label: 'Stellaris' },
  { value: 'hoi4', label: 'Hearts of Iron IV' },
  { value: 'vic3', label: 'Victoria 3' },
  { value: 'ck3', label: 'Crusader Kings III' },
  { value: 'eu4', label: 'Europa Universalis IV' },
];

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
];

function errorMessage(error) {
  return getCopilotWorkflowError(error).message;
}

export default function useInlineLocalizationWorkflow({ initialArgs, onStarted, onRecoveryAction }) {
  const [folderPath, setFolderPath] = useState(initialArgs.folder_path || '');
  const [projectName, setProjectName] = useState(initialArgs.project_name || '');
  const [gameId, setGameId] = useState(initialArgs.game_id || 'vic3');
  const [sourceLanguage, setSourceLanguage] = useState(initialArgs.source_language || 'en');
  const [targetLanguages, setTargetLanguages] = useState(() => (
    initialArgs.target_languages
    || initialArgs.target_lang_codes
    || [initialArgs.target_language || 'zh-CN']
  ));
  const [provider, setProvider] = useState(initialArgs.api_provider || 'lm_studio');
  const [model, setModel] = useState(initialArgs.model || 'local-model');
  const [assistantProviders, setAssistantProviders] = useState([]);
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [preparationError, setPreparationError] = useState('');
  const [resolvedProject, setResolvedProject] = useState(null);
  const shouldResolveProject = Boolean(
    initialArgs.project_mode === 'existing'
    || initialArgs.project_id
    || (initialArgs.project_name && !initialArgs.folder_path),
  );
  const [resolvingProject, setResolvingProject] = useState(shouldResolveProject);
  const [batchSize, setBatchSize] = useState(10);
  const [concurrency, setConcurrency] = useState(1);
  const [rpm, setRpm] = useState(40);
  const [useResume, setUseResume] = useState(true);
  const [useMainGlossary, setUseMainGlossary] = useState(true);
  const [workshopEnabled, setWorkshopEnabled] = useState(true);
  const [plan, setPlan] = useState(null);
  const [planInvalidation, setPlanInvalidation] = useState(null);
  const [partialSuccess, setPartialSuccess] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const inferredName = useMemo(() => {
    const normalized = folderPath.replace(/[\\/]+$/, '');
    return normalized.split(/[\\/]/).pop() || 'New Mod';
  }, [folderPath]);

  useEffect(() => {
    setLoadingSettings(true);
    fetchCopilotSettings().then((data) => {
      setAssistantProviders(data.providers || []);
      if (!initialArgs.api_provider) setProvider(data.settings?.provider || 'lm_studio');
      if (!initialArgs.model) setModel(data.settings?.model || 'local-model');
    }).catch((err) => {
      if (!initialArgs.api_provider || !initialArgs.model) {
        setPreparationError(`无法读取小助手的 Provider / 模型设置：${errorMessage(err)}`);
      }
    }).finally(() => setLoadingSettings(false));
  }, [initialArgs.api_provider, initialArgs.model]);

  useEffect(() => {
    if (!shouldResolveProject) return undefined;
    let cancelled = false;
    setResolvingProject(true);
    projectService.getActiveProjects().then((response) => {
      const projects = normalizeRecordArrayPayload(response.data, ['projects', 'items', 'data', 'results']);
      const resolution = resolveCopilotProject(projects, {
        game_id: initialArgs.game_id,
        project_id: initialArgs.project_id,
        project_name: initialArgs.project_name,
      });
      if (cancelled) return;
      if (!resolution.project) {
        setPreparationError(resolution.matchCount
          ? '找到多个可能的项目，无法安全确定要使用哪一个。请提供完整项目名称，或从项目页面重新发起。'
          : '找不到对话中指定的已有项目。请确认项目仍处于启用状态。');
        return;
      }
      const project = resolution.project;
      setResolvedProject(project);
      setFolderPath(project.source_path || '');
      setProjectName(project.name || '');
      setGameId(project.game_id || '');
      setSourceLanguage(project.source_language || '');
      setTargetLanguages((current) => current.filter((code) => code !== project.source_language));
    }).catch((err) => {
      if (!cancelled) setPreparationError(errorMessage(err));
    }).finally(() => {
      if (!cancelled) setResolvingProject(false);
    });
    return () => { cancelled = true; };
  }, [initialArgs.game_id, initialArgs.project_id, initialArgs.project_mode,
    initialArgs.project_name, shouldResolveProject]);

  const providerOptions = assistantProviders.length
    ? assistantProviders.map((item) => ({ value: item.id, label: item.name }))
    : [{ value: 'lm_studio', label: 'LM Studio' }];
  const selectedProvider = assistantProviders.find((item) => item.id === provider);
  const modelOptions = (selectedProvider?.models || []).map((item) => ({ value: item, label: item }));
  const gameLabel = GAMES.find((item) => item.value === gameId || (
    item.value === 'vic3' && gameId === 'victoria3'
  ))?.label || gameId;
  const sourceLanguageLabel = LANGUAGES.find((item) => item.value === sourceLanguage)?.label || sourceLanguage;
  const availableTargetLanguages = LANGUAGES.filter((item) => item.value !== sourceLanguage);

  const changeProvider = (value) => {
    const nextProvider = assistantProviders.find((item) => item.id === value);
    setProvider(value);
    setModel(nextProvider?.default_model || nextProvider?.models?.[0] || '');
  };

  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected !== 'string') return;
    setFolderPath(selected);
    if (!projectName) {
      const normalized = selected.replace(/[\\/]+$/, '');
      setProjectName(normalized.split(/[\\/]/).pop() || 'New Mod');
    }
  };

  const translationOptions = useMemo(() => ({
    api_provider: provider,
    model,
    batch_size_limit: batchSize,
    concurrency_limit: concurrency,
    rpm_limit: rpm,
    use_resume: useResume,
    use_main_glossary: useMainGlossary,
    embedded_workshop_enabled: workshopEnabled,
  }), [batchSize, concurrency, model, provider, rpm, useMainGlossary, useResume, workshopEnabled]);

  const buildPlan = useCallback(async () => {
    setBusy(true);
    setError('');
    setPlanInvalidation(null);
    setPartialSuccess(null);
    try {
      setPlan(resolvedProject
        ? await planInitialTranslationWorkflow({
          project_id: resolvedProject.project_id,
          target_lang_codes: targetLanguages,
          ...translationOptions,
        })
        : await planLocalizationWorkflow({
          folder_path: folderPath,
          project_name: projectName || inferredName,
          game_id: gameId,
          source_language: sourceLanguage,
          target_language: targetLanguages[0],
          import_mode: 'copy',
          ...translationOptions,
        }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [folderPath, gameId, inferredName, projectName, resolvedProject, sourceLanguage, targetLanguages,
    translationOptions]);

  const approve = useCallback(async () => {
    if (!plan || planInvalidation) return;
    setBusy(true);
    setError('');
    try {
      const result = resolvedProject
        ? await executeInitialTranslationWorkflow(plan.plan_id)
        : await executeGuidedLocalizationWorkflow(plan.plan_id);
      if (
        result?.code === 'project_created_translation_not_started'
        || result?.workflow_status === 'project_created_translation_not_started'
        || result?.partial_success === true
      ) {
        const createdProject = result.project || {};
        setResolvedProject({
          ...createdProject,
          project_id: createdProject.project_id,
          name: createdProject.name || projectName || inferredName,
          source_path: createdProject.source_path || folderPath,
          game_id: createdProject.game_id || gameId,
          source_language: createdProject.source_language || sourceLanguage,
        });
        setPartialSuccess(result);
        return;
      }
      onStarted({
        taskId: result.task_id,
        projectId: resolvedProject?.project_id || result.project?.project_id,
        projectName: resolvedProject?.name || result.project?.name || projectName || inferredName,
        gameId,
        sourceLanguage,
        targetLanguage: targetLanguages[0],
        targetLanguages,
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
      if (typeof window !== 'undefined' && result.task_id) {
        window.dispatchEvent(new CustomEvent('remis:task-created', {
          detail: { taskId: result.task_id, source: 'copilot' },
        }));
      }
    } catch (err) {
      const workflowError = getCopilotWorkflowError(err);
      setError(workflowError.message);
      if (workflowError.invalidApproval) {
        setPlanInvalidation(workflowError);
      }
    } finally {
      setBusy(false);
    }
  }, [model, batchSize, concurrency, folderPath, gameId, inferredName, onStarted, plan,
    planInvalidation, projectName, resolvedProject, rpm, sourceLanguage, targetLanguages,
    useMainGlossary, useResume, workshopEnabled, provider]);

  const regeneratePlan = useCallback(() => {
    setPlan(null);
    setError('');
    setPlanInvalidation(null);
    setPartialSuccess(null);
    return buildPlan();
  }, [buildPlan]);

  const resetPlan = useCallback(() => {
    setPlan(null);
    setPlanInvalidation(null);
    setPartialSuccess(null);
    setError('');
  }, []);

  const openRecoveredProject = useCallback(() => {
    const projectId = partialSuccess?.project?.project_id;
    if (!projectId || !onRecoveryAction) return;
    onRecoveryAction({
      action: 'open_initial_translation',
      args: { project_id: projectId },
    });
  }, [onRecoveryAction, partialSuccess]);

  return {
    approve, availableTargetLanguages, batchSize, browse, buildPlan, busy, changeProvider,
    concurrency, error, folderPath, gameLabel, inferredName, model, modelOptions, plan,
    openRecoveredProject, partialSuccess, planInvalidation, regeneratePlan, resetPlan,
    loadingSettings, preparationError, projectName, provider, providerOptions, resolvedProject,
    resolvingProject, rpm,
    setBatchSize, setConcurrency, setModel, setPlan, setRpm, setTargetLanguages,
    setUseMainGlossary, setUseResume, setWorkshopEnabled, sourceLanguage,
    sourceLanguageLabel, targetLanguages, useMainGlossary, useResume, workshopEnabled,
  };
}
