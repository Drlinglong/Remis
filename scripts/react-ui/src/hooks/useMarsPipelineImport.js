import { useEffect, useRef, useState } from 'react';
import service from '../services/marsPipelineService';

export const pipelineError = (error) => error?.response?.data?.detail?.message
  || error?.message || 'Request failed';

export function useMarsPipelineImport(onCreated, projectName = '') {
  const [state, setState] = useState({ path: '', previousRun: '', deliveryMode: 'source_copy',
    approved: [], plan: null, inspection: null, busy: false, error: '' });
  const epoch = useRef(0);
  useEffect(() => {
    epoch.current += 1;
    setState((old) => ({ ...old, plan: null, inspection: null, error: '', busy: false }));
  }, [projectName]);
  useEffect(() => () => { epoch.current += 1; }, []);
  const update = (field, value) => {
    epoch.current += 1;
    setState((old) => ({ ...old, [field]: value, plan: null, error: '', busy: false,
      ...(field === 'path' || field === 'previousRun' ? { approved: [], inspection: null } : {}) }));
  };
  const plan = async (reviewIds = state.approved, deliveryMode = state.deliveryMode) => {
    const version = ++epoch.current;
    setState((old) => ({ ...old, busy: true, error: '', plan: null, deliveryMode }));
    try {
      const { data } = await service.planImport({ archive_path: state.path, name: projectName,
        previous_run_id: state.previousRun || null, approved_ids: reviewIds,
        delivery_mode: deliveryMode });
      if (version === epoch.current) setState((old) => ({ ...old, plan: data, inspection: data,
        deliveryMode: data.selected_delivery_mode || deliveryMode,
        approved: reviewIds, busy: false }));
    } catch (error) {
      if (version === epoch.current) setState((old) => ({ ...old, error: pipelineError(error), busy: false }));
    }
  };
  const execute = async () => {
    if (!state.plan || state.busy) return;
    const version = ++epoch.current;
    setState((old) => ({ ...old, busy: true, error: '' }));
    try {
      const { data } = await service.import(state.plan.plan_id);
      if (version !== epoch.current) return;
      if (data.status !== 'prepared') {
        setState((old) => ({ ...old, busy: false, plan: null,
          error: `${(data.warnings || []).join(' ')} Project: ${data.project_id || ''}` }));
        return;
      }
      setState((old) => ({ ...old, busy: false, plan: null }));
      onCreated?.(data.project_id);
    } catch (error) {
      if (version === epoch.current) setState((old) => ({ ...old, error: pipelineError(error), busy: false }));
    }
  };
  return { ...state, name: projectName, update, preview: plan, execute };
}
