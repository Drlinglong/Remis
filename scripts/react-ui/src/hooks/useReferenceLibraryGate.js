import { useCallback, useState } from 'react';

import translationService from '../services/translationService';


export function useReferenceLibraryGate({ enabled, explicitPath, gameId }) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [bypassed, setBypassed] = useState(false);

  const check = useCallback(async ({ skip = false } = {}) => {
    if (!enabled || explicitPath || bypassed || skip) return false;
    try {
      const response = await translationService.getReferenceLibraryStatus();
      const available = response.data?.libraries?.some(
        (library) => library.game_id === gameId && library.available,
      );
      if (available) return false;
      setPromptOpen(true);
      return true;
    } catch (error) {
      console.warn('Failed to check reference library status; continuing without prompt.', error);
      return false;
    }
  }, [bypassed, enabled, explicitPath, gameId]);

  const reset = useCallback(() => {
    setBypassed(false);
    setPromptOpen(false);
  }, []);

  const continueWithoutReference = useCallback((continueAction) => {
    setBypassed(true);
    setPromptOpen(false);
    return continueAction();
  }, []);

  return {
    bypassed,
    check,
    continueWithoutReference,
    promptOpen,
    reset,
    setPromptOpen,
  };
}
