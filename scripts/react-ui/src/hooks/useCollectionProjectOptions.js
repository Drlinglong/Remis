import { useCallback, useRef, useState } from 'react';
import api from '../utils/api';

const base = '/api/translation-collections';

export function useCollectionProjectOptions({ capture, isCurrent, reportError }) {
  const [projectOptions, setProjectOptions] = useState({});
  const [optionsLoading, setOptionsLoading] = useState({});
  const inFlight = useRef(new Map());
  const optionsRef = useRef(projectOptions);
  optionsRef.current = projectOptions;

  const resetRequests = useCallback(() => {
    inFlight.current.clear();
    setOptionsLoading({});
  }, []);
  const invalidateMembers = useCallback((members) => {
    setProjectOptions((current) => {
      const next = { ...current };
      (members || []).forEach((member) => { delete next[member.project_id]; });
      return next;
    });
  }, []);
  const loadProjectOptions = useCallback((projectId, force = false) => {
    if (!force && optionsRef.current[projectId]) return Promise.resolve(optionsRef.current[projectId]);
    const { life, selection } = capture();
    const existing = inFlight.current.get(projectId);
    if (existing?.life === life && existing.selection === selection) return existing.request;
    setOptionsLoading((current) => ({ ...current, [projectId]: true }));
    const request = api.get(`${base}/project-options/${encodeURIComponent(projectId)}`)
      .then(({ data }) => {
        if (isCurrent(life, selection)) setProjectOptions((current) => ({ ...current, [projectId]: data }));
        return data;
      })
      .catch((cause) => {
        if (isCurrent(life, selection)) reportError(cause);
        return null;
      })
      .finally(() => {
        if (inFlight.current.get(projectId)?.request === request) {
          inFlight.current.delete(projectId);
          if (isCurrent(life, selection)) setOptionsLoading((current) => ({ ...current, [projectId]: false }));
        }
      });
    inFlight.current.set(projectId, { life, selection, request });
    return request;
  }, [capture, isCurrent, reportError]);

  return { projectOptions, optionsLoading, loadProjectOptions, resetRequests, invalidateMembers };
}
