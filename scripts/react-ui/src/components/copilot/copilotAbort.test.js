import { describe, expect, it } from 'vitest';
import { isCopilotRequestCancellation, toAssistantUiAbortError } from './copilotAbort';

describe('assistant-ui Copilot abort bridge', () => {
  it('converts Axios cancellation after route unmount to assistant-ui AbortError', () => {
    const controller = new AbortController();
    controller.abort();

    const error = toAssistantUiAbortError(
      { name: 'CanceledError', code: 'ERR_CANCELED' },
      controller.signal,
    );

    expect(isCopilotRequestCancellation(error, controller.signal)).toBe(true);
    expect(error).toMatchObject({ name: 'AbortError' });
  });

  it('does not rewrite a real request failure', () => {
    const error = new Error('provider unavailable');

    expect(toAssistantUiAbortError(error, new AbortController().signal)).toBe(error);
  });

  it('recognizes a native AbortError even when the signal is already detached', () => {
    const error = new Error('The operation was aborted');
    error.name = 'AbortError';

    expect(isCopilotRequestCancellation(error, new AbortController().signal)).toBe(true);
    expect(toAssistantUiAbortError(error, new AbortController().signal)).toMatchObject({
      name: 'AbortError',
    });
  });
});
