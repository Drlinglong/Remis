/**
 * assistant-ui treats an Error named AbortError as an expected cancelled run.
 * Axios uses CanceledError/ERR_CANCELED for the same AbortSignal transition.
 */
export function isCopilotRequestCancellation(error, abortSignal) {
  return Boolean(
    abortSignal?.aborted
      || error?.name === 'AbortError'
      || error?.name === 'CanceledError'
      || error?.code === 'ABORT_ERR'
      || error?.code === 'ERR_CANCELED',
  );
}

export function toAssistantUiAbortError(error, abortSignal) {
  if (!isCopilotRequestCancellation(error, abortSignal)) {
    return error;
  }
  const abortError = new Error('Copilot request cancelled');
  abortError.name = 'AbortError';
  return abortError;
}
