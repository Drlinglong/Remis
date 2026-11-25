import { useCallback, useLayoutEffect, useRef } from 'react';

// Each channel accepts only its newest response. Invalidate all channels when
// their owner changes; unmount also revokes pending requests.
export function useRequestScope() {
  const generation = useRef(0);
  const channels = useRef(new Map());
  const invalidate = useCallback(() => { generation.current += 1; }, []);
  const begin = useCallback((channel) => {
    const owner = generation.current;
    const request = (channels.current.get(channel) || 0) + 1;
    channels.current.set(channel, request);
    return () => owner === generation.current && request === channels.current.get(channel);
  }, []);
  useLayoutEffect(() => invalidate, [invalidate]);
  return { begin, invalidate };
}
