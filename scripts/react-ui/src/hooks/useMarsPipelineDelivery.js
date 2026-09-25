import { useEffect, useRef, useState } from 'react';
import service from '../services/marsPipelineService';
import { pipelineError } from './useMarsPipelineImport';

const initial = { options: null, selected: [], mode: 'source_copy', plan: null, result: null, busy: false, error: '' };

export function useMarsPipelineDelivery(projectId, gameId) {
  const [state, setState] = useState(initial);
  const epoch = useRef(0);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const version = ++epoch.current;
    const abort = new AbortController();
    setState(initial);
    if (gameId === 'surviving_mars' && projectId) {
      service.options(projectId, { signal: abort.signal }).then(({ data }) => {
        if (version === epoch.current) setState({ ...initial, options: data,
          mode: data.selected_delivery_mode || initial.mode });
      }).catch((error) => {
        if (version === epoch.current && !abort.signal.aborted) setState({ ...initial, error: pipelineError(error) });
      });
    }
    return () => { epoch.current += 1; abort.abort(); };
  }, [projectId, gameId, refresh]);
  const update = (field, value) => {
    epoch.current += 1;
    setState((old) => ({ ...old, [field]: value, plan: null, result: null, error: '', busy: false }));
  };
  const run = async (execute) => {
    if (state.busy || (execute && !state.plan)) return;
    const version = ++epoch.current;
    setState((old) => ({ ...old, busy: true, error: '', result: null }));
    try {
      const outputs = state.options.translation_outputs.filter((item) => state.selected.includes(item.output_folder_name))
        .map((item) => ({ output_folder_name: item.output_folder_name, language_code: item.language_code }));
      const { data } = execute ? await service.export(projectId, state.plan.plan_id)
          : await service.planExport(projectId, { mode: state.mode, outputs });
      if (version === epoch.current) setState((old) => ({ ...old, busy: false,
        ...(execute ? { result: data, plan: null } : { plan: data }) }));
    } catch (error) {
      if (version === epoch.current) setState((old) => ({ ...old, busy: false, error: pipelineError(error), plan: null }));
    }
  };
  const publicationChanged = () => {
    epoch.current += 1;
    setState((old) => ({ ...old, plan: null, result: null, busy: false, error: '' }));
    setRefresh((value) => value + 1);
  };
  return { ...state, update, preview: () => run(false), execute: () => run(true),
    reload: () => setRefresh((value) => value + 1), publicationChanged };
}
