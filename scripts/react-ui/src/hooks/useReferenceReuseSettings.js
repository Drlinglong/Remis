import { useCallback, useRef, useState } from 'react';
import translationService from '../services/translationService';
import { toggleReferenceExclusion } from '../utils/referenceReuse';

export const useReferenceReuseSettings = (t) => {
  const [referenceReuseEnabled, setReferenceReuseEnabled] = useState(true);
  const [referenceLocalizationPath, setReferenceLocalizationPath] = useState('');
  const [referencePreviewEntries, setReferencePreviewEntries] = useState([]);
  const [referencePreviewError, setReferencePreviewError] = useState('');
  const [referencePreviewLoading, setReferencePreviewLoading] = useState(false);
  const [referenceReuseExcludedEntries, setReferenceReuseExcludedEntries] = useState([]);
  const previewRequestRef = useRef(0);

  const changeReferenceLocalizationPath = useCallback((value) => {
    previewRequestRef.current += 1;
    setReferenceLocalizationPath(value);
    setReferencePreviewEntries([]);
    setReferenceReuseExcludedEntries([]);
    setReferencePreviewError('');
    setReferencePreviewLoading(false);
  }, []);

  const previewReferenceReuse = useCallback(async ({
    projectId, sourceLangCode, sourcePath = null, targetLangCodes,
  }) => {
    const requestId = ++previewRequestRef.current;
    setReferencePreviewLoading(true);
    setReferencePreviewError('');
    try {
      const response = await translationService.previewReferenceReuse({
        project_id: projectId,
        source_lang_code: sourceLangCode,
        target_lang_codes: targetLangCodes,
        localization_path: referenceLocalizationPath || null,
        custom_source_path: sourcePath || null,
      });
      if (previewRequestRef.current === requestId) {
        setReferencePreviewEntries(response.data?.matches || []);
      }
      return response.data;
    } catch (error) {
      const detail = error?.response?.data?.detail || error?.message || t('notification.error_generic');
      if (previewRequestRef.current === requestId) setReferencePreviewError(String(detail));
      return null;
    } finally {
      if (previewRequestRef.current === requestId) setReferencePreviewLoading(false);
    }
  }, [referenceLocalizationPath, t]);

  const toggleReferenceEntry = useCallback((entry, shouldReuse) => {
    setReferenceReuseExcludedEntries((current) => (
      toggleReferenceExclusion(current, entry, shouldReuse)
    ));
  }, []);

  const resetReferencePreview = useCallback(() => {
    previewRequestRef.current += 1;
    setReferencePreviewEntries([]);
    setReferenceReuseExcludedEntries([]);
    setReferencePreviewError('');
    setReferencePreviewLoading(false);
  }, []);

  return {
    changeReferenceLocalizationPath,
    referenceLocalizationPath,
    referencePreviewEntries,
    referencePreviewError,
    referencePreviewLoading,
    referenceReuseExcludedEntries,
    referenceReuseEnabled,
    previewReferenceReuse,
    resetReferencePreview,
    setReferenceLocalizationPath,
    setReferencePreviewEntries,
    setReferenceReuseExcludedEntries,
    setReferenceReuseEnabled,
    toggleReferenceEntry,
  };
};
