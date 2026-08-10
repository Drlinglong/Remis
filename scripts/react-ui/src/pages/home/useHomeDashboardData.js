import { useCallback, useEffect, useRef, useState } from 'react';

import api from '../../utils/api';
import { EMPTY_DASHBOARD_DATA, normalizeDashboardData } from './homeDashboardModel';

export function useHomeDashboardData({ language } = {}) {
  const requestRef = useRef(0);
  const [state, setState] = useState({
    phase: 'loading',
    data: EMPTY_DASHBOARD_DATA,
    error: null,
  });

  const refresh = useCallback(async () => {
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setState((previous) => ({ ...previous, phase: 'loading', error: null }));
    try {
      const { data } = await api.get('/api/system/stats');
      if (requestRef.current !== requestId) return;
      setState({ phase: 'ready', data: normalizeDashboardData(data), error: null });
    } catch (error) {
      if (requestRef.current !== requestId) return;
      setState((previous) => ({ ...previous, phase: 'error', error }));
    }
  }, []);

  useEffect(() => {
    refresh();
    return () => {
      requestRef.current += 1;
    };
  }, [language, refresh]);

  return { ...state, refresh };
}
