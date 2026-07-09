import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { usePersistentState } from './usePersistentState';

/**
 * Hook for managing Monaco editor content and file data loading.
 */
export const useEditorContent = () => {
    const { t } = useTranslation();
    const [entries, setEntries] = useState([]);
    const [originalContentStr, setOriginalContentStr] = useState('');
    const [aiContentStr, setAiContentStr] = useState('');
    const [finalContentStr, setFinalContentStr] = useState('');
    const [loading, setLoading] = useState(false);
    const [fileInfo, setFileInfo] = useState(null);
    const [keyChangeWarning, setKeyChangeWarning] = useState(false);
    const [baselineKeys, setBaselineKeys] = useState(new Set());

    // Draft cache
    const [draftCache, setDraftCache] = usePersistentState('remis_draft_cache', null);

    // Use ref to access latest draftCache in loadEditorData without adding it as dependency
    const draftCacheRef = useRef(draftCache);
    useEffect(() => {
        draftCacheRef.current = draftCache;
    }, [draftCache]);

    // Refs for editors and scroll sync
    const originalEditorRef = useRef(null);
    const aiEditorRef = useRef(null);
    const finalEditorRef = useRef(null);
    const isScrolling = useRef(false);

    const formatLocalizationEntry = useCallback((key, value) => {
        const match = String(key || '').match(/^(.+?)(?::(\d+))?$/);
        const baseKey = match?.[1] || key;
        const version = match?.[2];
        const versionText = version === undefined ? ':' : `:${version}`;
        return `${baseKey}${versionText} "${value || ''}"`;
    }, []);

    const alignEntries = useCallback((entries) => {
        let originalStr = "";
        let aiStr = "";
        let finalStr = "";

        entries.forEach(e => {
            const origText = e.original || "";
            const aiText = e.translation || "";
            const finalText = e.translation || "";

            const WRAP_WIDTH = 60;
            const calcLines = (text) => {
                if (!text) return 1;
                let len = 0;
                for (let i = 0; i < text.length; i++) {
                    len += text.charCodeAt(i) > 255 ? 2 : 1;
                }
                return Math.max(1, Math.ceil(len / WRAP_WIDTH));
            };

            const maxL = Math.max(calcLines(origText), calcLines(aiText));
            const pad1 = Math.max(0, maxL - calcLines(origText));
            const pad2 = Math.max(0, maxL - calcLines(aiText));

            originalStr += formatLocalizationEntry(e.key, origText) + "\n".repeat(pad1) + "\n";
            aiStr += formatLocalizationEntry(e.key, aiText) + "\n".repeat(pad2) + "\n";
            finalStr += `${formatLocalizationEntry(e.key, finalText)}\n`;
        });

        return { originalStr, aiStr, finalStr };
    }, [formatLocalizationEntry]);

    const parseEditorContentToEntries = useCallback((content) => {
        const entries = [];
        const regex = /^\s*([^:\s]+)\s*:\s*([0-9]*)\s*"((?:[^"\\]|\\.)*)"/gm;
        let match;
        const headers = ["l_english", "l_simp_chinese", "l_french", "l_german", "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"];

        while ((match = regex.exec(content)) !== null) {
            const keyBase = match[1].trim();
            const version = match[2].trim();
            if (headers.some(h => keyBase.startsWith(h))) continue;
            const fullKey = version ? `${keyBase}:${version}` : keyBase;
            entries.push({ key: fullKey, value: match[3] });
        }
        return entries;
    }, []);

    const extractLocalizationKeys = useCallback((content) => {
        const keys = new Set();
        const regex = /^\s*([^:\s]+)\s*:\s*([0-9]*)\s*"/gm;
        let match;
        const headers = ["l_english", "l_simp_chinese", "l_french", "l_german", "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"];

        while ((match = regex.exec(content || '')) !== null) {
            const keyBase = match[1].trim();
            const version = match[2].trim();
            if (headers.some(h => keyBase.startsWith(h))) continue;
            const fullKey = version ? `${keyBase}:${version}` : keyBase;
            keys.add(fullKey);
        }
        return keys;
    }, []);

    const getProofreadingLoadErrorMessage = useCallback((detail) => {
        const fallback = typeof detail === 'string' && detail
            ? detail
            : 'Failed to load file data.';
        if (!detail || typeof detail !== 'object' || !detail.code) {
            return fallback;
        }

        const defaults = {
            project_not_found: 'Cannot load proofreading data because the project no longer exists.',
            file_not_indexed: 'Cannot load proofreading data because this file is not in the current project file index. Refresh project files and try again.',
            file_path_missing: 'Cannot load proofreading data because this project file has no recorded localization path. Refresh or repair the project metadata.',
            file_path_not_found: detail.message || 'Cannot load proofreading data because the indexed localization file no longer exists on disk.',
            data_preparation_failed: 'Cannot prepare proofreading data for this file. Check that the source and translation files are valid localization files.',
        };

        return t(`proofreading.errors.${detail.code}`, {
            defaultValue: detail.message || defaults[detail.code] || fallback,
        });
    }, [t]);

    const loadEditorData = useCallback(async (pId, sourceFilePath, targetId) => {
        setLoading(true);
        try {
            if (sourceFilePath && sourceFilePath.trim() !== '') {
                try {
                    const readRes = await api.post('/api/system/read_file', { file_path: sourceFilePath });
                    setOriginalContentStr(readRes.data.content || "");
                } catch (readError) {
                    console.error("Failed to read source file:", readError);
                    setOriginalContentStr("");
                }
            } else {
                setOriginalContentStr("");
            }

            if (targetId) {
                const resTarget = await api.get(`/api/proofread/${pId}/${targetId}`);
                const data = resTarget.data;
                setFileInfo({ path: data.file_path, project_id: pId, file_id: targetId });
                setEntries(data.entries || []);

                let contentToSet = "";
                if (data.ai_content) {
                    contentToSet = data.final_content || data.ai_content;
                    setAiContentStr(data.ai_content);
                } else if (data.file_content) {
                    contentToSet = data.file_content;
                    setAiContentStr(data.file_content);
                } else {
                    const { aiStr, finalStr } = alignEntries(data.entries || []);
                    setAiContentStr(aiStr);
                    contentToSet = finalStr;
                }

                // [DISABLED] Auto-restore causes confusion if disk file updates. User requested to clear this cache behavior.
                // const cache = draftCacheRef.current;
                // if (cache && cache.projectId === pId && cache.fileId === targetId) {
                //     contentToSet = cache.content;
                //     notifications.show({ title: 'Draft Restored', message: 'Restored unsaved changes.', color: 'blue' });
                // }

                setBaselineKeys(extractLocalizationKeys(contentToSet));
                setFinalContentStr(contentToSet);
            } else {
                setAiContentStr("");
                setFinalContentStr("");
                setEntries([]);
                setFileInfo(null);
                setBaselineKeys(new Set());
            }
        } catch (error) {
            console.error("Failed to load editor data", error);
            const detail = error.response?.data?.detail;
            const message = getProofreadingLoadErrorMessage(detail);
            notifications.show({ title: 'Error', message, color: 'red' });
        } finally {
            setLoading(false);
        }
    }, [alignEntries, extractLocalizationKeys, getProofreadingLoadErrorMessage]); // draftCache removed from deps

    // Auto-save draft
    useEffect(() => {
        if (fileInfo && finalContentStr !== undefined) {
            const timer = setTimeout(() => {
                setDraftCache({
                    projectId: fileInfo.project_id,
                    fileId: fileInfo.file_id,
                    content: finalContentStr,
                    timestamp: Date.now()
                });
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [finalContentStr, fileInfo, setDraftCache]);

    // Key change detection
    useEffect(() => {
        if (!baselineKeys.size || !finalContentStr) {
            setKeyChangeWarning(false);
            return;
        }

        const currentKeys = extractLocalizationKeys(finalContentStr);

        let hasChanges = currentKeys.size !== baselineKeys.size;
        if (!hasChanges) {
            for (let k of currentKeys) {
                if (!baselineKeys.has(k)) {
                    hasChanges = true;
                    break;
                }
            }
        }
        setKeyChangeWarning(hasChanges);
    }, [baselineKeys, extractLocalizationKeys, finalContentStr]);

    // Sync scroll
    useEffect(() => {
        const editors = [originalEditorRef, aiEditorRef, finalEditorRef];
        const disposables = [];

        const syncScroll = (sourceEditor, e) => {
            if (isScrolling.current) return;
            isScrolling.current = true;
            const { scrollTop, scrollLeft } = e;
            editors.forEach(ref => {
                if (ref.current && ref.current !== sourceEditor) {
                    ref.current.setScrollPosition({ scrollTop, scrollLeft });
                }
            });
            setTimeout(() => { isScrolling.current = false; }, 50);
        };

        const attachListeners = () => {
            editors.forEach(ref => {
                if (ref.current) {
                    const disposable = ref.current.onDidScrollChange((e) => syncScroll(ref.current, e));
                    disposables.push(disposable);
                }
            });
        };

        const timer = setTimeout(attachListeners, 500);
        return () => { clearTimeout(timer); disposables.forEach(d => d && d.dispose()); };
    }, [originalContentStr, aiContentStr, finalContentStr]);

    return {
        entries,
        originalContentStr,
        aiContentStr,
        finalContentStr,
        setFinalContentStr,
        loading,
        fileInfo,
        keyChangeWarning,
        loadEditorData,
        parseEditorContentToEntries,
        originalEditorRef,
        aiEditorRef,
        finalEditorRef
    };
};
