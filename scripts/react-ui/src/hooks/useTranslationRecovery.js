import { useCallback, useEffect, useRef, useState } from 'react';

import api from '../utils/api';

export const TRANSLATION_RECOVERY_ACTIONS = Object.freeze({
  CLEAR: 'clear_checkpoint',
  RESUME: 'resume_task',
  START_OVER: 'start_over_task',
});

const IDLE_STATE = Object.freeze({
  phase: 'idle',
  recovery: null,
  error: null,
  pendingAction: null,
});

const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

export const buildTranslationRecoveryEndpoint = (projectId) => (
  `/api/projects/${encodeURIComponent(projectId)}/translation-recovery`
);

export const buildTranslationCheckpointEndpoint = (projectId) => (
  `/api/projects/${encodeURIComponent(projectId)}/translation-checkpoint`
);

export const buildTranslationRecoveryActionEndpoint = (taskId, action) => {
  if (!taskId) throw new Error('A task ID is required for a recovery action.');
  if (![TRANSLATION_RECOVERY_ACTIONS.RESUME, TRANSLATION_RECOVERY_ACTIONS.START_OVER].includes(action)) {
    throw new Error(`Unsupported translation recovery action: ${action}`);
  }
  const endpointAction = action === TRANSLATION_RECOVERY_ACTIONS.RESUME ? 'resume' : 'start-over';
  return `/api/tasks/${encodeURIComponent(taskId)}/${endpointAction}`;
};

const getRecoveryBody = (payload) => {
  const body = isRecord(payload?.data) ? payload.data : payload;
  if (isRecord(body?.recovery)) return body.recovery;
  return isRecord(body) ? body : {};
};

export const normalizeTranslationRecovery = (payload) => {
  const body = getRecoveryBody(payload);
  const task = isRecord(body.task) ? body.task : {};
  const checkpoint = isRecord(body.checkpoint)
    ? body.checkpoint
    : isRecord(task.checkpoint) ? task.checkpoint : null;
  const allowedActions = Array.isArray(body.allowed_actions)
    ? body.allowed_actions
    : Array.isArray(task.allowed_actions) ? task.allowed_actions : [];

  return {
    ...body,
    task_id: body.task_id ?? task.task_id ?? null,
    project_id: body.project_id ?? task.project_id ?? null,
    status: body.status ?? task.status ?? null,
    stage: body.stage ?? task.stage ?? null,
    progress: body.progress ?? task.progress ?? 0,
    checkpoint,
    allowed_actions: allowedActions,
  };
};

export const isRecoveryActionAllowed = (recovery, action) => (
  Array.isArray(recovery?.allowed_actions) && recovery.allowed_actions.includes(action)
);

export class TranslationRecoveryActionError extends Error {
  constructor(action) {
    super(`Backend does not allow translation recovery action: ${action}`);
    this.name = 'TranslationRecoveryActionError';
    this.code = 'recovery_action_not_allowed';
    this.action = action;
  }
}

export function useTranslationRecovery(projectId, {
  apiClient = api,
  autoLoad = true,
} = {}) {
  const [state, setState] = useState(IDLE_STATE);
  const requestSequence = useRef(0);

  const loadRecovery = useCallback(async (requestedProjectId = projectId) => {
    if (!requestedProjectId) {
      setState(IDLE_STATE);
      return null;
    }

    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setState((previous) => ({ ...previous, phase: 'loading', error: null }));

    try {
      const response = await apiClient.get(buildTranslationRecoveryEndpoint(requestedProjectId));
      const recovery = normalizeTranslationRecovery(response);
      if (requestSequence.current === sequence) {
        setState({ phase: 'ready', recovery, error: null, pendingAction: null });
      }
      return recovery;
    } catch (error) {
      if (requestSequence.current === sequence) {
        setState({ phase: 'error', recovery: null, error, pendingAction: null });
      }
      throw error;
    }
  }, [apiClient, projectId]);

  useEffect(() => {
    if (autoLoad) void loadRecovery().catch(() => {});
  }, [autoLoad, loadRecovery]);

  const performAction = useCallback(async (action, payload = {}) => {
    const taskId = state.recovery?.task_id;
    if (!isRecoveryActionAllowed(state.recovery, action)) {
      const error = new TranslationRecoveryActionError(action);
      setState((previous) => ({ ...previous, error }));
      throw error;
    }

    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setState((previous) => ({ ...previous, phase: 'action', pendingAction: action, error: null }));

    try {
      const response = await apiClient.post(
        buildTranslationRecoveryActionEndpoint(taskId, action),
        payload,
      );
      const recovery = normalizeTranslationRecovery(response);
      if (requestSequence.current === sequence) {
        setState({ phase: 'ready', recovery, error: null, pendingAction: null });
      }
      return response.data;
    } catch (error) {
      if (requestSequence.current === sequence) {
        setState((previous) => ({ ...previous, phase: 'error', error, pendingAction: null }));
      }
      throw error;
    }
  }, [apiClient, state.recovery]);

  const resume = useCallback((payload) => performAction(
    TRANSLATION_RECOVERY_ACTIONS.RESUME,
    payload,
  ), [performAction]);

  const startOver = useCallback((payload) => performAction(
    TRANSLATION_RECOVERY_ACTIONS.START_OVER,
    payload,
  ), [performAction]);

  const clearCheckpoint = useCallback(async () => {
    const action = TRANSLATION_RECOVERY_ACTIONS.CLEAR;
    if (!isRecoveryActionAllowed(state.recovery, action)) {
      const error = new TranslationRecoveryActionError(action);
      setState((previous) => ({ ...previous, error }));
      throw error;
    }

    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setState((previous) => ({ ...previous, phase: 'action', pendingAction: action, error: null }));

    try {
      const response = await apiClient.delete(buildTranslationCheckpointEndpoint(projectId));
      const recovery = normalizeTranslationRecovery(response);
      if (requestSequence.current === sequence) {
        setState({ phase: 'ready', recovery, error: null, pendingAction: null });
      }
      return response.data;
    } catch (error) {
      if (requestSequence.current === sequence) {
        setState((previous) => ({ ...previous, phase: 'error', error, pendingAction: null }));
      }
      throw error;
    }
  }, [apiClient, projectId, state.recovery]);

  return {
    ...state,
    isLoading: state.phase === 'loading',
    isActionPending: state.phase === 'action',
    canResume: isRecoveryActionAllowed(state.recovery, TRANSLATION_RECOVERY_ACTIONS.RESUME),
    canStartOver: isRecoveryActionAllowed(state.recovery, TRANSLATION_RECOVERY_ACTIONS.START_OVER),
    canClearCheckpoint: isRecoveryActionAllowed(
      state.recovery,
      TRANSLATION_RECOVERY_ACTIONS.CLEAR,
    ),
    loadRecovery,
    refresh: loadRecovery,
    resume,
    startOver,
    clearCheckpoint,
  };
}
