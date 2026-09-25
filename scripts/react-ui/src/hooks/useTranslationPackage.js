import { useCallback, useEffect, useRef, useState } from 'react';
import translationPackageService from '../services/translationPackageService';

const initialState = {
  options: null,
  loading: false,
  planning: false,
  generating: false,
  error: null,
  plan: null,
  result: null,
  errorMessage: null,
  outputFolderName: '',
  targetLanguage: '',
  sourceModId: '',
  sourceModTitle: '',
  author: '',
};

const getApiError = (error) => {
  const detail = error?.response?.data?.detail;
  return {
    code: detail?.code || error?.response?.data?.code || 'unexpected',
    message: typeof detail?.message === 'string' ? detail.message : '',
  };
};

export function useTranslationPackage(projectId, gameId) {
  const [state, setState] = useState(initialState);
  const requestEpochRef = useRef(0);

  useEffect(() => {
    if (!projectId || gameId !== 'surviving_mars') {
      setState(initialState);
      return undefined;
    }

    const controller = new AbortController();
    const requestEpoch = ++requestEpochRef.current;
    let current = true;
    setState({ ...initialState, loading: true });
    translationPackageService.getOptions(projectId, { signal: controller.signal })
      .then(({ data }) => {
        if (!current || requestEpoch !== requestEpochRef.current) return;
        const sourceMod = data?.source_mod || {};
        const outputs = Array.isArray(data?.translation_outputs) ? data.translation_outputs : [];
        const languages = Array.isArray(data?.languages) ? data.languages : [];
        const initialLanguage = outputs[0]?.language_code || languages[0]?.code || '';
        setState({
          ...initialState,
          options: data,
          loading: false,
          outputFolderName: outputs[0]?.output_folder_name || '',
          targetLanguage: initialLanguage,
          sourceModId: sourceMod.id || '',
          sourceModTitle: sourceMod.title || '',
        });
      })
      .catch((error) => {
        if (!current || requestEpoch !== requestEpochRef.current
          || error.name === 'CanceledError' || error.name === 'AbortError') return;
        const apiError = getApiError(error);
        setState({ ...initialState, loading: false, error: apiError.code, errorMessage: apiError.message });
      });

    return () => {
      current = false;
      requestEpochRef.current += 1;
      controller.abort();
    };
  }, [gameId, projectId]);

  const updateField = useCallback((field, value) => {
    requestEpochRef.current += 1;
    setState((current) => ({
      ...current,
      [field]: value,
      ...(field === 'outputFolderName' ? {
        targetLanguage: current.options?.translation_outputs?.find((output) => output.output_folder_name === value)?.language_code
          || current.targetLanguage,
      } : {}),
      plan: null,
      result: null,
      error: null,
      errorMessage: null,
      planning: false,
      generating: false,
    }));
  }, []);

  const createPlan = useCallback(async () => {
    const requestEpoch = ++requestEpochRef.current;
    const sourceMod = state.options?.source_mod || {};
    setState((current) => ({ ...current, planning: true, error: null, errorMessage: null, plan: null, result: null }));
    try {
      const response = await translationPackageService.createPlan(projectId, {
        output_folder_name: state.outputFolderName,
        target_language: state.targetLanguage,
        ...(!sourceMod.id && state.sourceModId.trim() ? { source_mod_id: state.sourceModId.trim() } : {}),
        ...(!sourceMod.title && state.sourceModTitle.trim() ? { source_mod_title: state.sourceModTitle.trim() } : {}),
        ...(state.author.trim() ? { author: state.author.trim() } : {}),
      });
      if (requestEpoch !== requestEpochRef.current) return;
      setState((current) => ({ ...current, planning: false, plan: response.data, result: null }));
    } catch (error) {
      if (requestEpoch !== requestEpochRef.current) return;
      const apiError = getApiError(error);
      setState((current) => ({
        ...current,
        planning: false,
        error: apiError.code,
        errorMessage: apiError.message,
        plan: null,
      }));
    }
  }, [projectId, state.author, state.options, state.outputFolderName, state.sourceModId, state.sourceModTitle, state.targetLanguage]);

  const generatePackage = useCallback(async () => {
    if (!state.plan?.plan_id || state.plan?.requires_approval !== true) return;
    const requestEpoch = ++requestEpochRef.current;
    setState((current) => ({ ...current, generating: true, error: null, errorMessage: null, result: null }));
    try {
      const response = await translationPackageService.createPackage(projectId, {
        plan_id: state.plan.plan_id,
        approved: true,
      });
      if (requestEpoch !== requestEpochRef.current) return;
      setState((current) => ({ ...current, generating: false, result: response.data, plan: null }));
    } catch (error) {
      if (requestEpoch !== requestEpochRef.current) return;
      const apiError = getApiError(error);
      setState((current) => ({
        ...current,
        generating: false,
        error: apiError.code,
        errorMessage: apiError.message,
        plan: ['stale_plan', 'approval_required'].includes(apiError.code) ? null : current.plan,
      }));
    }
  }, [projectId, state.plan]);

  return { ...state, updateField, createPlan, generatePackage };
}

export default useTranslationPackage;
