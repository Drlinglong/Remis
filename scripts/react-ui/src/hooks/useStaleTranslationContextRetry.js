import { useCallback, useState } from 'react';
import {
  addStaleContextChoice,
  getStaleContextDetail,
} from '../services/translationContextStaleService';

export function useStaleTranslationContextRetry() {
  const [pending, setPending] = useState(null);

  const submit = useCallback(async ({ payload, request, onSuccess, onError, onCancel }) => {
    try {
      const response = await request(payload);
      await onSuccess(response);
      return response;
    } catch (error) {
      const detail = getStaleContextDetail(error);
      if (detail) {
        setPending({ payload, request, onSuccess, onError, onCancel, detail });
        return false;
      }
      if (onError) onError(error);
      else throw error;
      return false;
    }
  }, []);

  const choose = useCallback(async (choice) => {
    if (!pending) return false;
    const current = pending;
    const retryPayload = addStaleContextChoice(current.payload, current.detail, choice);
    if (!retryPayload) {
      current.onError?.(new Error('The archive response did not include a current source snapshot.'));
      setPending(null);
      return false;
    }
    setPending(null);
    try {
      const response = await current.request(retryPayload);
      await current.onSuccess(response);
      return response;
    } catch (error) {
      const detail = getStaleContextDetail(error);
      if (detail) {
        setPending({ ...current, detail });
      } else {
        current.onError(error);
      }
      return false;
    }
  }, [pending]);

  const cancel = useCallback(() => {
    if (pending?.onCancel) pending.onCancel();
    setPending(null);
  }, [pending]);

  return {
    cancel,
    choose,
    detail: pending?.detail || null,
    opened: Boolean(pending),
    submit,
  };
}
