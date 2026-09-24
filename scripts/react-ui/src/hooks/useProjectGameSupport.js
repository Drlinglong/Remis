import { useEffect, useState } from 'react';
import projectService from '../services/projectService';
import { hasStructuredGameSupport } from '../utils/gameSupportPolicy';

const emptyState = { data: null, error: null, loading: false };

export function useProjectGameSupport(projectId, gameId) {
  const [state, setState] = useState(emptyState);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!projectId || !hasStructuredGameSupport(gameId)) {
      setState(emptyState);
      return undefined;
    }

    const controller = new AbortController();
    let current = true;
    setState({ data: null, error: null, loading: true });

    projectService.getGameSupport(projectId, { signal: controller.signal })
      .then((response) => {
        if (current) setState({ data: response.data, error: null, loading: false });
      })
      .catch((error) => {
        if (!current || error.name === 'CanceledError' || error.name === 'AbortError') return;
        setState({ data: null, error, loading: false });
      });

    return () => {
      current = false;
      controller.abort();
    };
  }, [gameId, projectId, refreshKey]);

  return { ...state, retry: () => setRefreshKey((value) => value + 1) };
}
