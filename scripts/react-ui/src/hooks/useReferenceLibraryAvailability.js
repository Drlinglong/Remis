import { useEffect, useState } from 'react';

import translationService from '../services/translationService';

export default function useReferenceLibraryAvailability({ enabled, gameId }) {
  const [availability, setAvailability] = useState('unknown');

  useEffect(() => {
    let cancelled = false;
    if (!enabled || !gameId) {
      setAvailability('unknown');
      return undefined;
    }

    setAvailability('loading');
    translationService.getReferenceLibraryStatus()
      .then((response) => {
        if (cancelled) return;
        const available = response.data?.libraries?.some(
          (library) => library.game_id === gameId && library.available,
        );
        setAvailability(available ? 'available' : 'missing');
      })
      .catch((error) => {
        if (cancelled) return;
        console.warn('Failed to check reference library availability.', error);
        setAvailability('unknown');
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, gameId]);

  return availability;
}
