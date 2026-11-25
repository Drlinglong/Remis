import { useState } from 'react';
import modelArenaService from '../services/modelArenaService';
import { apiErrorDetail } from '../utils/apiErrorDetail';
import { useRequestScope } from './useRequestScope';

function downloadArtifact(response, runId) {
  const blob = response.data instanceof Blob
    ? response.data
    : new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `remis-model-arena-${runId}.json`;
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(url);
  }
}

export function useModelArenaExport(errorFallback) {
  const { begin, invalidate } = useRequestScope();
  const [session, setSession] = useState({ runId: null, mode: 'evidence' });

  const closePreview = () => {
    invalidate();
    setSession(({ mode }) => ({ runId: null, mode }));
  };

  const loadPreview = async (target, mode = session.mode) => {
    const runId = target?.run_id;
    if (!runId || session.exporting) return;
    const isCurrent = begin('preview');
    setSession({ runId, mode, loading: true });
    try {
      const artifact = await modelArenaService.getExportPreview(runId, mode);
      if (!isCurrent()) return;
      if (artifact?.export_mode !== mode || artifact?.arena_run?.run_id !== runId) {
        setSession({ runId, mode, error: errorFallback });
        return;
      }
      setSession({ runId, mode, artifact });
    } catch (error) {
      if (isCurrent()) setSession({ runId, mode, error: apiErrorDetail(error, errorFallback) });
    }
  };

  const exportRun = async () => {
    const { runId, mode, artifact, exporting } = session;
    if (!artifact || exporting) return;
    const isCurrent = begin('preview');
    setSession({ runId, mode, artifact, exporting: true });
    try {
      const response = await modelArenaService.exportRun(runId, mode);
      downloadArtifact(response, runId);
      const path = response.headers?.['x-remis-export-path'];
      if (path) await modelArenaService.openExportPath(decodeURIComponent(path));
      if (isCurrent()) setSession({ runId, mode, artifact });
    } catch (error) {
      if (isCurrent()) setSession({ runId, mode, artifact, error: apiErrorDetail(error, errorFallback) });
    }
  };

  return { session, closePreview, loadPreview, exportRun };
}
