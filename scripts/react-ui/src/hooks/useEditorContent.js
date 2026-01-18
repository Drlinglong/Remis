import { useState, useRef, useEffect, useCallback } from 'react';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { usePersistentState } from './usePersistentState';

/**
 * Hook for managing Monaco editor content and file data loading.
 */
export const useEditorContent = () => {
    const [entries, setEntries] = useState([]);
    const [originalContentStr, setOriginalContentStr] = useState('');
    const [aiContentStr, setAiContentStr] = useState('');
    const [finalContentStr, setFinalContentStr] = useState('');
    const [loading, setLoading] = useState(false);
    const [fileInfo, setFileInfo] = useState(null);
    const [keyChangeWarning, setKeyChangeWarning] = useState(false);

    // Draft cache
    const [draftCache, setDraftCache] = usePersistentState('remis_draft_cache', null);

    // Refs for editors and scroll sync
    const originalEditorRef = useRef(null);
    const aiEditorRef = useRef(null);
    const finalEditorRef = useRef(null);
    const isScrolling = useRef(false);

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

            originalStr += `${e.key}:0 "${origText}"` + "\n".repeat(pad1) + "\n";
            aiStr += `${e.key}:0 "${aiText}"` + "\n".repeat(pad2) + "\n";
            finalStr += `${e.key}:0 "${finalText}"\n`;
        });

        return { originalStr, aiStr, finalStr };
    }, []);

    const parseEditorContentToEntries = useCallback((content) => {
        const entries = [];
        const regex = /^\s*([\w\.-]+)\s*:\s*(\d*)\s*"((?:[^"\\]|\\.)*)"/gm;
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

                // Restore draft if exists
                if (draftCache && draftCache.projectId === pId && draftCache.fileId === targetId) {
                    contentToSet = draftCache.content;
                    notifications.show({ title: 'Draft Restored', message: 'Restored unsaved changes.', color: 'blue' });
                }

                setFinalContentStr(contentToSet);
            } else {
                setAiContentStr("");
                setFinalContentStr("");
                setEntries([]);
                setFileInfo(null);
            }
        } catch (error) {
            console.error("Failed to load editor data", error);
            notifications.show({ title: 'Error', message: "Failed to load file data.", color: 'red' });
        } finally {
            setLoading(false);
        }
    }, [alignEntries, draftCache]);

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
        if (!entries.length || !finalContentStr) {
            setKeyChangeWarning(false);
            return;
        }

        const currentKeys = new Set();
        const regex = /^\s*([\w\.-]+)\s*:\s*(\d*)\s*"/gm;
        let match;
        const headers = ["l_english", "l_simp_chinese", "l_french", "l_german", "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"];

        while ((match = regex.exec(finalContentStr)) !== null) {
            const keyBase = match[1].trim();
            const version = match[2].trim();
            if (headers.some(h => keyBase.startsWith(h))) continue;
            const fullKey = version ? `${keyBase}:${version}` : keyBase;
            currentKeys.add(fullKey);
        }

        const originalKeys = new Set(entries.map(e => e.key));
        let hasChanges = currentKeys.size !== originalKeys.size;
        if (!hasChanges) {
            for (let k of currentKeys) {
                if (!originalKeys.has(k)) {
                    hasChanges = true;
                    break;
                }
            }
        }
        setKeyChangeWarning(hasChanges);
    }, [finalContentStr, entries]);

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
