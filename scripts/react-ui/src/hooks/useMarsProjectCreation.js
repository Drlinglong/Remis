import { useEffect, useRef, useState } from 'react';
import service from '../services/marsPipelineService';
import { pipelineError } from './useMarsPipelineImport';

const initial = { busy: false, error: '', stage: '' };

export function useMarsProjectCreation({ opened, game, path, name, language, onCreated, createEditable }) {
  const [state, setState] = useState(initial);
  const epoch = useRef(0);
  const inFlight = useRef(false);
  useEffect(() => {
    epoch.current += 1;
    setState(initial);
  }, [opened, game, path, name, language]);
  useEffect(() => () => { epoch.current += 1; }, []);
  const create = async () => {
    if (inFlight.current || !name.trim() || !path.trim() || !language) return;
    inFlight.current = true;
    const version = ++epoch.current;
    const current = () => version === epoch.current;
    setState({ ...initial, busy: true, stage: 'inspect' });
    try {
      const { data: input } = await service.inspectInput(path);
      if (!current()) return;
      if (input.kind === 'editable_folder') {
        setState(initial);
        await createEditable();
        return;
      }
      const { data: plan } = await service.planImport({ archive_path: input.archive_path, name,
        source_language: language, source_column: 'Text', delivery_mode: 'source_copy' });
      if (!current()) return;
      if ((plan.source_blockers || []).length || !plan.allowed_actions?.includes('approve_preparation')) {
        setState({ ...initial,
          error: (plan.source_blockers || []).map((item) => item.message).join(' ')
            || 'Source preparation requires review. Open Advanced source options.' });
        return;
      }
      setState({ ...initial, busy: true, stage: 'prepare' });
      const { data: result } = await service.import(plan.plan_id);
      if (!current()) return;
      if (result.status !== 'prepared') {
        setState({ ...initial, error: (result.warnings || []).join(' ') || 'Project preparation did not complete.' });
        return;
      }
      setState(initial);
      onCreated?.(result.project_id);
    } catch (error) {
      if (current()) setState({ ...initial, error: pipelineError(error) });
    } finally {
      inFlight.current = false;
    }
  };
  return { ...state, create };
}
