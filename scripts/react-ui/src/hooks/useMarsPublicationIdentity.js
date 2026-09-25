import { useEffect, useRef, useState } from 'react';
import service from '../services/marsPipelineService';
import { pipelineError } from './useMarsPipelineImport';

const initial = { identity: null, steamId: '', loading: false, saving: false, error: '' };

export function useMarsPublicationIdentity(projectId) {
  const [state, setState] = useState(initial);
  const epoch = useRef(0);

  useEffect(() => {
    const version = ++epoch.current;
    const controller = new AbortController();
    setState({ ...initial, loading: Boolean(projectId) });
    if (projectId) {
      service.publication(projectId, { signal: controller.signal }).then(({ data }) => {
        if (version === epoch.current) setState({ ...initial, identity: data, steamId: data.steam_id || '' });
      }).catch((error) => {
        if (version === epoch.current && !controller.signal.aborted) {
          setState({ ...initial, error: pipelineError(error) });
        }
      });
    }
    return () => { epoch.current += 1; controller.abort(); };
  }, [projectId]);

  const updateSteamId = (steamId) => setState((old) => ({ ...old, steamId, error: '' }));
  const bind = async () => {
    const steamId = state.steamId.trim();
    if (!projectId || state.saving || state.loading || state.error || !state.identity
      || state.identity.status !== 'unbound' || !/^\d+$/.test(steamId) || BigInt(steamId) <= 0n) return false;
    const version = ++epoch.current;
    setState((old) => ({ ...old, saving: true, error: '' }));
    try {
      const { data } = await service.bindPublication(projectId, {
        approved: true,
        expected_revision: state.identity.revision,
        steam_id: steamId,
      });
      if (version !== epoch.current) return false;
      setState((old) => ({ ...old, identity: data, steamId: data.steam_id || steamId, saving: false }));
      return true;
    } catch (error) {
      if (version === epoch.current) setState((old) => ({ ...old, saving: false, error: pipelineError(error) }));
      return false;
    }
  };

  return { ...state, updateSteamId, bind };
}
