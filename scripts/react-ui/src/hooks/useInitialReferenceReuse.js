import { useCallback, useEffect, useRef, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import translationService from '../services/translationService';
import { toggleReferenceExclusion } from '../utils/referenceReuse';

export const useInitialReferenceReuse = ({
  excludedEntries,
  localizationPath,
  projectId,
  setFieldValue,
  sourceLangCode,
  t,
  targetLangCodes,
}) => {
  const [previewEntries, setPreviewEntries] = useState([]);
  const [previewError, setPreviewError] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewRequestRef = useRef(0);
  const contextKey = [projectId, sourceLangCode, ...targetLangCodes].join('|');
  const contextKeyRef = useRef(contextKey);

  const resetPreview = useCallback(() => {
    previewRequestRef.current += 1;
    setFieldValue('reference_reuse_excluded_entries', []);
    setPreviewEntries([]);
    setPreviewError('');
    setPreviewLoading(false);
  }, [setFieldValue]);

  useEffect(() => {
    if (contextKeyRef.current === contextKey) return;
    contextKeyRef.current = contextKey;
    resetPreview();
  }, [contextKey, resetPreview]);

  const changePath = useCallback((value) => {
    setFieldValue('reference_localization_path', value);
    resetPreview();
  }, [resetPreview, setFieldValue]);

  const selectFolder = useCallback(async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: t('translation_config.reference_select_folder'),
    });
    if (selected && typeof selected === 'string') changePath(selected);
  }, [changePath, t]);

  const preview = useCallback(async () => {
    const requestId = ++previewRequestRef.current;
    setPreviewLoading(true);
    setPreviewError('');
    try {
      const response = await translationService.previewReferenceReuse({
        project_id: projectId,
        source_lang_code: sourceLangCode,
        target_lang_codes: targetLangCodes,
        localization_path: localizationPath,
      });
      if (previewRequestRef.current === requestId) {
        setPreviewEntries(response.data?.matches || []);
      }
      return response.data;
    } catch (error) {
      const detail = error?.response?.data?.detail || error?.message || t('notification.error_generic');
      if (previewRequestRef.current === requestId) setPreviewError(String(detail));
      return null;
    } finally {
      if (previewRequestRef.current === requestId) setPreviewLoading(false);
    }
  }, [localizationPath, projectId, sourceLangCode, t, targetLangCodes]);

  const toggleEntry = useCallback((entry, shouldReuse) => {
    setFieldValue(
      'reference_reuse_excluded_entries',
      toggleReferenceExclusion(excludedEntries, entry, shouldReuse),
    );
  }, [excludedEntries, setFieldValue]);

  return {
    changePath,
    preview,
    previewEntries,
    previewError,
    previewLoading,
    selectFolder,
    toggleEntry,
  };
};
