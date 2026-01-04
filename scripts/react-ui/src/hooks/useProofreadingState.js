import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { notifications } from '@mantine/notifications';
import { usePersistentState } from './usePersistentState';
import api from '../utils/api';
import { toParadoxLang } from '../utils/paradoxMapping';
import { groupFiles as performGrouping } from '../utils/fileGrouping';

/**
 * 校对页面的核心状态管理 Hook
 * 集中管理项目选择、文件导航、编辑器内容、验证和保存逻辑
 */
const useProofreadingState = () => {
    const [searchParams, setSearchParams] = useSearchParams();

    // ==================== 项目相关状态 ====================
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);

    const [projectFilter, setProjectFilter] = usePersistentState('proofread_project_filter', '');

    // ==================== 文件导航状态 ====================
    const [sourceFiles, setSourceFiles] = useState([]);
    const [targetFilesMap, setTargetFilesMap] = useState({});
    const [currentSourceFile, setCurrentSourceFile] = useState(null);
    const [currentTargetFile, setCurrentTargetFile] = useState(null);

    // ==================== 编辑器内容状态 ====================
    const [entries, setEntries] = useState([]);
    const [originalContentStr, setOriginalContentStr] = useState('');
    const [aiContentStr, setAiContentStr] = useState('');
    const [finalContentStr, setFinalContentStr] = useState('');

    // ==================== 验证与保存状态 ====================
    const [validationResults, setValidationResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [stats, setStats] = useState({ error: 0, warning: 0 });
    const [keyChangeWarning, setKeyChangeWarning] = useState(false);
    const [saveModalOpen, setSaveModalOpen] = useState(false);
    const [fileInfo, setFileInfo] = useState(null);

    // ==================== Linter 模式状态 ====================
    const [linterContent, setLinterContent] = useState('');
    const [linterGameId, setLinterGameId] = useState('1');
    const [linterResults, setLinterResults] = useState([]);
    const [linterLoading, setLinterLoading] = useState(false);
    const [linterError, setLinterError] = useState(null);

    // Persistence: Unsaved Draft Cache
    // We only track the single most recent file being edited
    const [draftCache, setDraftCache] = usePersistentState('remis_draft_cache', null);

    // Effect: Auto-save draft content
    useEffect(() => {
        if (fileInfo && finalContentStr !== undefined) {
            // Only save if we have meaningful content or at least loaded content
            // Using a timeout to debounce could be better, but for now direct is fine for minimal latency
            const timer = setTimeout(() => {
                setDraftCache({
                    projectId: fileInfo.project_id,
                    fileId: fileInfo.file_id,
                    content: finalContentStr,
                    timestamp: Date.now()
                });
            }, 500); // 500ms debounce
            return () => clearTimeout(timer);
        }
    }, [finalContentStr, fileInfo, setDraftCache]);

    // Persistence: Last active session
    useEffect(() => {
        const pId = searchParams.get('projectId');
        const fId = searchParams.get('fileId');
        if (pId && fId) {
            sessionStorage.setItem('remis_last_proofread_session', JSON.stringify({ projectId: pId, fileId: fId }));
        }
    }, [searchParams]);

    // Persistence: Resume session if URL is clean
    useEffect(() => {
        const pId = searchParams.get('projectId');
        const fId = searchParams.get('fileId');

        if (!pId && !fId) {
            try {
                const saved = sessionStorage.getItem('remis_last_proofread_session');
                if (saved) {
                    const parsed = JSON.parse(saved);
                    // Restore session immediately if we have a saved ID
                    if (parsed.projectId) {
                        setSearchParams({ projectId: parsed.projectId, fileId: parsed.fileId }, { replace: true });
                    }
                }
            } catch (e) { console.error("Failed to restore session", e); }
        }
    }, [searchParams, setSearchParams]);

    // ==================== 编辑器引用 ====================
    const originalEditorRef = useRef(null);
    const aiEditorRef = useRef(null);
    const finalEditorRef = useRef(null);
    const isScrolling = useRef(false);

    // ==================== 数据获取函数 ====================
    const fetchProjects = useCallback(async () => {
        try {
            const res = await api.get('/api/projects?status=active');
            setProjects(res.data);
        } catch (error) {
            console.error("Failed to load projects", error);
        }
    }, []);

    // ==================== 辅助解析函数 ====================
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

            const l1 = calcLines(origText);
            const l2 = calcLines(aiText);
            const maxL = Math.max(l1, l2);

            const pad1 = Math.max(0, maxL - l1);
            const pad2 = Math.max(0, maxL - l2);

            originalStr += `${e.key}:0 "${origText}"` + "\n".repeat(pad1) + "\n";
            aiStr += `${e.key}:0 "${aiText}"` + "\n".repeat(pad2) + "\n";
            finalStr += `${e.key}:0 "${finalText}"\n`;
        });

        return { originalStr, aiStr, finalStr };
    }, []);

    const parseEditorContentToEntries = useCallback((content) => {
        const entries = [];
        // Support keys with dots, underscores, and hyphens. Support optional digit index.
        // Match key followed by optional spaces, then colon, then optional spaces, then optional version digits
        const regex = /^\s*([\w\.-]+)\s*:\s*(\d*)\s*"((?:[^"\\]|\\.)*)"/gm;
        let match;
        const headers = ["l_english", "l_simp_chinese", "l_french", "l_german", "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"];

        while ((match = regex.exec(content)) !== null) {
            const keyBase = match[1].trim();
            const version = match[2].trim();
            if (headers.some(h => keyBase.startsWith(h))) continue; // Skip headers

            // Universal Normalization: key:version (no spaces)
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
                try {
                    const savedRaw = sessionStorage.getItem('remis_draft_cache');
                    if (savedRaw) {
                        const draft = JSON.parse(savedRaw);
                        if (draft && draft.projectId === pId && draft.fileId === targetId) {
                            contentToSet = draft.content;
                            notifications.show({ title: 'Draft Restored', message: 'Restored unsaved changes from session cache.', color: 'blue' });
                        }
                    }
                } catch (e) { console.error("Failed to restore draft", e); }

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
    }, [alignEntries]);

    // ==================== 业务逻辑函数 ====================
    const groupFiles = useCallback((files) => {
        if (!selectedProject) return;

        const { sources, targetsMap } = performGrouping(files, selectedProject);

        setSourceFiles(sources);
        setTargetFilesMap(targetsMap);

        // Note: Selection logic moved to useEffect to prevent race conditions.
    }, [selectedProject]);

    const fetchProjectFiles = useCallback(async (projectId) => {
        try {
            const res = await api.get(`/api/project/${projectId}/files`);
            if (res.data) {
                groupFiles(res.data);
            }
        } catch (error) {
            console.error("Failed to load project files", error);
        }
    }, [groupFiles]);

    // ==================== 事件处理器 ====================
    const handleProjectSelect = useCallback((val) => {
        const proj = projects.find(p => p.project_id === val);
        if (proj) {
            setSelectedProject(proj);
            setSearchParams({ projectId: proj.project_id });
        }
    }, [projects, setSearchParams]);

    const handleSourceFileChange = useCallback((val) => {
        const source = sourceFiles.find(s => s.file_id === val);
        if (source) {
            setCurrentSourceFile(source);
            const targets = targetFilesMap[source.file_id];
            if (targets && targets.length > 0) {
                setCurrentTargetFile(targets[0]);
                loadEditorData(selectedProject.project_id, source.file_path, targets[0].file_id);
                setSearchParams({ projectId: selectedProject.project_id, fileId: targets[0].file_id });
            } else {
                setCurrentTargetFile(null);
                loadEditorData(selectedProject.project_id, source.file_path, null);
                setSearchParams({ projectId: selectedProject.project_id, fileId: source.file_id });
            }
        }
    }, [sourceFiles, targetFilesMap, selectedProject, loadEditorData, setSearchParams]);

    const handleTargetFileChange = useCallback((val) => {
        if (!currentSourceFile) return;
        const targets = targetFilesMap[currentSourceFile.file_id];
        const target = targets.find(t => t.file_id === val);
        if (target) {
            setCurrentTargetFile(target);
            loadEditorData(selectedProject.project_id, currentSourceFile.file_path, target.file_id);
            setSearchParams({ projectId: selectedProject.project_id, fileId: target.file_id });
        }
    }, [currentSourceFile, targetFilesMap, selectedProject, loadEditorData, setSearchParams]);

    const handleValidate = useCallback(async () => {
        setLoading(true);
        setValidationResults([]);
        try {
            const parsed = parseEditorContentToEntries(finalContentStr);
            let virtualContent = "";
            parsed.forEach(e => {
                virtualContent += ` ${e.key}:0 "${e.value}"\n`;
            });

            const response = await api.post('/api/validate/localization', {
                game_id: selectedProject.game_id || 'victoria3',
                content: virtualContent,
                source_lang_code: 'en_US'
            });

            const issues = response.data;
            setValidationResults(issues);

            const errors = issues.filter(i => i.level === 'error').length;
            const warnings = issues.filter(i => i.level === 'warning').length;
            setStats({ error: errors, warning: warnings });

            if (errors === 0 && warnings === 0) {
                notifications.show({ title: 'Perfect', message: 'No issues found.', color: 'green' });
            } else {
                notifications.show({ title: 'Issues Found', message: `Found ${errors} errors and ${warnings} warnings.`, color: 'yellow' });
            }

        } catch (error) {
            console.error("Validation failed", error);
            notifications.show({ title: 'Error', message: "Validation failed.", color: 'red' });
        } finally {
            setLoading(false);
        }
    }, [finalContentStr, parseEditorContentToEntries]);

    const confirmSave = useCallback(async () => {
        setSaveModalOpen(false);
        setSaving(true);
        try {
            const parsedEntries = parseEditorContentToEntries(finalContentStr);

            const savePayload = {
                project_id: fileInfo.project_id,
                file_id: fileInfo.file_id,
                entries: parsedEntries.map(e => ({
                    key: e.key,
                    translation: e.value
                })),
                target_language: `l_${toParadoxLang(selectedProject.source_language || 'english')}` // Heuristic: default to source lang if unknown, or ideally user should select target
            };

            await api.post('/api/proofread/save', savePayload);

            notifications.show({ title: 'Saved', message: 'File saved successfully.', color: 'green' });

        } catch (error) {
            console.error("Save failed", error);
            notifications.show({ title: 'Error', message: "Failed to save file.", color: 'red' });
        } finally {
            setSaving(false);
        }
    }, [finalContentStr, fileInfo, parseEditorContentToEntries]);

    const handleSaveClick = useCallback(() => {
        if (keyChangeWarning) {
            setSaveModalOpen(true);
        } else {
            confirmSave();
        }
    }, [keyChangeWarning, confirmSave]);

    const handleOpenFolder = useCallback(async () => {
        if (!fileInfo || !fileInfo.path) return;
        try {
            const path = fileInfo.path.replace(/\\/g, '/');
            const dirPath = path.substring(0, path.lastIndexOf('/'));
            await api.post('/api/system/open_folder', { path: dirPath });
            notifications.show({ title: 'Success', message: 'Folder opened', color: 'green' });
        } catch (error) {
            notifications.show({ title: 'Error', message: 'Failed to open folder', color: 'red' });
        }
    }, [fileInfo]);

    const handleLinterValidate = useCallback(async () => {
        if (!linterContent.trim()) return;
        setLinterLoading(true);
        setLinterError(null);
        setLinterResults([]);
        try {
            const response = await api.post('/api/validate/localization', {
                game_id: linterGameId,
                content: linterContent,
                source_lang_code: 'en_US'
            });
            setLinterResults(response.data);
        } catch (err) {
            setLinterError("Failed to validate.");
        } finally {
            setLinterLoading(false);
        }
    }, [linterContent, linterGameId]);

    // ==================== 副作用 ====================
    // 初始化：获取项目列表
    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    // URL 参数同步 - 选中项目
    useEffect(() => {
        const pId = searchParams.get('projectId');
        if (pId && projects.length > 0 && !selectedProject) {
            const proj = projects.find(p => p.project_id === pId);
            if (proj) setSelectedProject(proj);
        }
    }, [searchParams, projects, selectedProject]);

    // URL 参数同步 - 选中文件 (Enforce URL source of truth)
    useEffect(() => {
        // Only run if we have data to select from
        if (sourceFiles.length > 0 && selectedProject) {
            const urlFileId = searchParams.get('fileId');

            let resolvedSource = null;
            let resolvedTarget = null;

            if (urlFileId) {
                // Try as source
                resolvedSource = sourceFiles.find(s => String(s.file_id) === String(urlFileId));
                if (resolvedSource) {
                    if (targetFilesMap[resolvedSource.file_id]?.length > 0) {
                        resolvedTarget = targetFilesMap[resolvedSource.file_id][0];
                    }
                } else {
                    // Try as target
                    for (const sId in targetFilesMap) {
                        const foundT = targetFilesMap[sId].find(t => String(t.file_id) === String(urlFileId));
                        if (foundT) {
                            resolvedSource = sourceFiles.find(s => String(s.file_id) === sId);
                            resolvedTarget = foundT;
                            break;
                        }
                    }
                }
            }

            // Fallback / Default logic
            if (!resolvedSource) {
                console.log("[Effect] No valid file resolved from URL. Defaulting to first file.");
                resolvedSource = sourceFiles[0];
                if (targetFilesMap[resolvedSource.file_id]?.length > 0) {
                    resolvedTarget = targetFilesMap[resolvedSource.file_id][0];
                }
            }

            if (resolvedSource) {
                // If selection mismatch, force update
                const isMismatch = !currentSourceFile ||
                    String(currentSourceFile.file_id) !== String(resolvedSource.file_id) ||
                    (resolvedTarget && (!currentTargetFile || String(currentTargetFile.file_id) !== String(resolvedTarget.file_id)));

                if (isMismatch) {
                    console.log(`[Effect] Applying selection: ${resolvedSource.file_path}`);
                    setCurrentSourceFile(resolvedSource);
                    setCurrentTargetFile(resolvedTarget);
                    loadEditorData(selectedProject.project_id, resolvedSource.file_path, resolvedTarget ? resolvedTarget.file_id : null);

                    // Sync URL if it differed (e.g. fallback or initial load)
                    const targetId = resolvedTarget ? resolvedTarget.file_id : resolvedSource.file_id;
                    if (String(urlFileId) !== String(targetId)) {
                        setSearchParams({ projectId: selectedProject.project_id, fileId: targetId }, { replace: true });
                    }
                }
            }
        }
    }, [searchParams, sourceFiles, targetFilesMap, selectedProject, currentSourceFile, currentTargetFile, loadEditorData, setSearchParams]);

    // 项目切换：获取文件
    useEffect(() => {
        if (selectedProject) {
            fetchProjectFiles(selectedProject.project_id);
        }
    }, [selectedProject, fetchProjectFiles]);

    // 键值修改检测
    useEffect(() => {
        if (!entries.length || !finalContentStr) return;

        // Regex to extract keys from content
        const currentKeys = new Set();
        // Match key followed by colon and optional version, allow spaces
        const regex = /^\s*([\w\.-]+)\s*:\s*(\d*)\s*"/gm;
        let match;
        const headers = ["l_english", "l_simp_chinese", "l_french", "l_german", "l_spanish", "l_russian", "l_polish", "l_japanese", "l_korean", "l_turkish", "l_braz_por"];

        while ((match = regex.exec(finalContentStr)) !== null) {
            const keyBase = match[1].trim();
            const version = match[2].trim();
            if (headers.some(h => keyBase.startsWith(h))) continue; // Skip headers

            const fullKey = version ? `${keyBase}:${version}` : keyBase;
            currentKeys.add(fullKey);
        }

        const originalKeys = new Set(entries.map(e => e.key));

        let hasChanges = false;
        if (currentKeys.size !== originalKeys.size) {
            hasChanges = true;
        } else {
            for (let k of currentKeys) {
                if (!originalKeys.has(k)) {
                    hasChanges = true;
                    break;
                }
            }
        }

        setKeyChangeWarning(hasChanges);
    }, [finalContentStr, entries]);

    // 同步滚动
    useEffect(() => {
        const editors = [originalEditorRef, aiEditorRef, finalEditorRef];
        const disposables = [];

        const syncScroll = (sourceEditor, e) => {
            if (isScrolling.current) return;
            isScrolling.current = true;
            const scrollTop = e.scrollTop;
            const scrollLeft = e.scrollLeft;
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

    // ==================== 返回接口 ====================
    return {
        // 项目相关
        projects,
        selectedProject,
        setSelectedProject,

        projectFilter,
        setProjectFilter,

        // 文件相关
        sourceFiles,
        targetFilesMap,
        currentSourceFile,
        currentTargetFile,
        setCurrentSourceFile,
        setCurrentTargetFile,

        // 编辑器内容
        originalContentStr,
        aiContentStr,
        finalContentStr,
        setFinalContentStr,

        // 验证与保存
        validationResults,
        stats,
        saving,
        loading,
        keyChangeWarning,
        saveModalOpen,
        setSaveModalOpen,
        fileInfo,

        // Linter 模式
        linterContent,
        setLinterContent,
        linterGameId,
        setLinterGameId,
        linterResults,
        linterLoading,
        linterError,

        // 引用
        originalEditorRef,
        aiEditorRef,
        finalEditorRef,

        // 事件处理器
        handleProjectSelect,
        handleSourceFileChange,
        handleTargetFileChange,
        handleValidate,
        handleSaveClick,
        confirmSave,
        handleLinterValidate,
        handleOpenFolder,
    };
};

export default useProofreadingState;
