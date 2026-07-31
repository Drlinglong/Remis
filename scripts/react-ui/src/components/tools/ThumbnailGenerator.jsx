import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import { Button, Grid, Paper, Stack, Text } from '@mantine/core';
import { save } from '@tauri-apps/plugin-dialog';
import html2canvas from 'html2canvas';

import './ThumbnailGenerator.css';
import { CoverCanvas } from '../steamWorkshop/cover/CoverCanvas';
import { CoverInspector } from '../steamWorkshop/cover/CoverInspector';
import { CoverToolbox } from '../steamWorkshop/cover/CoverToolbox';
import { CoverVersionPanel } from '../steamWorkshop/cover/CoverVersionPanel';
import { hydrateCoverCanvas, serializeCoverCanvas } from '../steamWorkshop/cover/coverCanvasState';
import { useCoverDraft } from '../steamWorkshop/cover/useCoverDraft';
import { useCoverEditor } from '../steamWorkshop/cover/useCoverEditor';
import { useCoverVersions } from '../steamWorkshop/cover/useCoverVersions';
import steamWorkshopCoverService from '../../services/steamWorkshopCoverService';

const translationLabels = (t) => ({
    toolboxTitle: t('thumbnail_generator.toolbox_title'),
    useProjectThumbnail: t('thumbnail_generator.use_project_thumbnail'),
    useProjectThumbnailTooltip: t('thumbnail_generator.use_project_thumbnail_tooltip'),
    projectThumbnailUnavailable: t('thumbnail_generator.project_thumbnail_unavailable'),
    addFlags: t('thumbnail_generator.add_flags'),
    addText: t('thumbnail_generator.add_text'),
    addAllFlags: t('thumbnail_generator.add_all_flags'),
    resetCanvas: t('thumbnail_generator.reset_canvas'),
    deleteCanvas: t('thumbnail_generator.delete_canvas'),
    inspectorTitle: t('thumbnail_generator.inspector_title'),
    backgroundColor: t('thumbnail_generator.background_color'),
    uploadBackground: t('thumbnail_generator.upload_background_image'),
    elementProperties: t('thumbnail_generator.element_properties'),
    textContent: t('thumbnail_generator.prop_text_content'),
    fontSize: t('thumbnail_generator.prop_font_size'),
    fontFamily: t('thumbnail_generator.prop_font_family'),
    color: t('thumbnail_generator.prop_color'),
    deleteElement: t('thumbnail_generator.delete_element'),
    uploadEmblem: t('thumbnail_generator.upload_custom_emblem'),
    placeholder: t('thumbnail_generator.canvas_placeholder'),
    dragHint: t('thumbnail_generator.drag_hint'),
    download: t('thumbnail_generator.download_thumbnail'),
    versionTitle: t('steam_workshop.cover.version_title', { defaultValue: '封面图版本' }),
    workspaceContext: t('steam_workshop.cover.workspace_context', { defaultValue: '发布工作区：{id}' }),
    projectDraft: t('steam_workshop.cover.project_draft', { defaultValue: '项目 {id} 的本机草稿' }),
    unboundDraft: t('steam_workshop.cover.unbound_draft', { defaultValue: '未绑定的本机草稿' }),
    draftSaved: t('steam_workshop.cover.draft_saved', { defaultValue: '草稿已于 {time} 自动保存' }),
    saveCandidate: t('steam_workshop.cover.save_candidate', { defaultValue: '保存候选版本' }),
    workspaceRequired: t('steam_workshop.cover.workspace_required', {
        defaultValue: '选择或创建发布工作区后才能保存正式版本。',
    }),
    historyTitle: t('steam_workshop.cover.history_title', { defaultValue: '版本历史' }),
    emptyHistory: t('steam_workshop.cover.empty_history', { defaultValue: '还没有封面图版本。' }),
    selected: t('steam_workshop.cover.selected', { defaultValue: '当前采用' }),
    loadForEditing: t('steam_workshop.cover.load_for_editing', { defaultValue: '载入编辑' }),
    useVersion: t('steam_workshop.cover.use_version', { defaultValue: '设为采用' }),
    requestFailed: t('steam_workshop.cover.request_failed', {
        defaultValue: '封面图版本操作失败，草稿仍保存在本机。',
    }),
});

const dataUrlToBytes = (dataUrl) => {
    const encoded = dataUrl.split(',', 2)[1] || '';
    const binary = window.atob(encoded);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
};

export const downloadDataUrl = (dataUrl) => {
    const bytes = dataUrlToBytes(dataUrl);
    const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    const link = document.createElement('a');
    link.download = 'thumbnail.png';
    link.href = url;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
};

export const saveThumbnail = async (dataUrl) => {
    if (!isTauri()) {
        downloadDataUrl(dataUrl);
        return;
    }
    const path = await save({
        defaultPath: 'thumbnail.png',
        filters: [{ name: 'PNG image', extensions: ['png'] }],
        title: '保存封面图',
    });
    if (!path) return;
    await invoke('save_thumbnail_png', { path, contents: Array.from(dataUrlToBytes(dataUrl)) });
};

const waitForPaint = () => new Promise((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
});

const ThumbnailGenerator = ({
    editCoverVersionId = null,
    projectId = null,
    workspaceId = null,
    currentCoverVersionId = null,
}) => {
    const { t } = useTranslation();
    const labels = translationLabels(t);
    const canvasContainerRef = useRef(null);
    const canvasLoadGenerationRef = useRef(0);
    const requestedVersionIdRef = useRef(null);
    const [projectThumbnailError, setProjectThumbnailError] = useState(null);
    const editor = useCoverEditor({ defaultText: t('thumbnail_generator.default_text') });
    const { replaceCanvas, selectedId, setSelectedId } = editor;
    const { draftSavedAt, draftError, clearCanvas: clearDraftCanvas } = useCoverDraft({
        workspaceId,
        projectId,
        canvasState: editor.canvasState,
        replaceCanvas: editor.replaceCanvas,
    });

    const loadCanvas = useCallback(async (canvas) => {
        const generation = canvasLoadGenerationRef.current + 1;
        canvasLoadGenerationRef.current = generation;
        const hydrated = await hydrateCoverCanvas(canvas);
        if (generation === canvasLoadGenerationRef.current) replaceCanvas(hydrated);
    }, [replaceCanvas]);
    const handleClearCanvas = useCallback(() => {
        canvasLoadGenerationRef.current += 1;
        clearDraftCanvas();
    }, [clearDraftCanvas]);
    const toolboxEditor = { ...editor, clearCanvas: handleClearCanvas };
    const versionState = useCoverVersions({
        workspaceId,
        currentVersionId: currentCoverVersionId,
        onLoadCanvas: loadCanvas,
    });
    const { loadVersion } = versionState;

    useEffect(() => {
        if (!editCoverVersionId) {
            requestedVersionIdRef.current = null;
            return;
        }
        if (requestedVersionIdRef.current === editCoverVersionId) return;

        requestedVersionIdRef.current = editCoverVersionId;
        // Keep the explicit id in the URL so refresh and deep links repeat this intentional load.
        loadVersion(editCoverVersionId);
    }, [editCoverVersionId, loadVersion]);

    const capturePng = useCallback(async () => {
        const previousSelection = selectedId;
        setSelectedId(null);
        await waitForPaint();
        try {
            if (!canvasContainerRef.current) throw new Error('cover_canvas_empty');
            const canvas = await html2canvas(canvasContainerRef.current, {
                backgroundColor: null,
                logging: false,
                useCORS: true,
            });
            return canvas.toDataURL('image/png');
        } finally {
            setSelectedId(previousSelection);
        }
    }, [selectedId, setSelectedId]);

    const saveCandidate = async () => {
        const pngDataUrl = await capturePng();
        await versionState.saveVersion({
            pngDataUrl,
            canvas: serializeCoverCanvas(editor.canvasState),
        });
    };
    const handleDownload = async () => saveThumbnail(await capturePng());
    const handleUseProjectThumbnail = async () => {
        if (!workspaceId || !projectId) return;
        try {
            await editor.setBackgroundImageFromSource(
                steamWorkshopCoverService.getProjectThumbnailUrl(workspaceId),
            );
            setProjectThumbnailError(null);
        } catch (_error) {
            setProjectThumbnailError(labels.projectThumbnailUnavailable);
        }
    };
    const handleDrop = (event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file?.type.startsWith('image/')) editor.addFileImage(file, 'mod');
    };
    const hasCanvasContent = editor.backgroundColor !== '#ffffff'
        || Boolean(editor.backgroundImage)
        || editor.elements.length > 0;

    return (
        <Stack data-remis-surface="surface" className="cover-editor-workspace">
            <Grid align="flex-start">
                <Grid.Col span={{ base: 12, md: 3 }}>
                    <CoverToolbox
                        canLoadProjectThumbnail={Boolean(workspaceId && projectId)}
                        editor={toolboxEditor}
                        labels={labels}
                        onLoadProjectThumbnail={handleUseProjectThumbnail}
                        projectThumbnailError={projectThumbnailError}
                    />
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }} className="cover-editor-center">
                    <Paper withBorder p="md" data-remis-surface="surface" className="cover-canvas-panel">
                        <CoverCanvas
                            canvasRef={canvasContainerRef}
                            editTextLabel={labels.textContent}
                            editor={editor}
                            onDrop={handleDrop}
                            onDragOver={(event) => event.preventDefault()}
                            onRequestBackground={() => editor.inputRefs.backgroundInputRef.current?.click()}
                            placeholder={labels.placeholder}
                            dragHint={labels.dragHint}
                        />
                        <Button
                            className="cover-canvas-action"
                            variant="light"
                            onClick={handleDownload}
                            disabled={!hasCanvasContent}
                        >
                            {labels.download}
                        </Button>
                    </Paper>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 3 }}>
                    <CoverInspector editor={editor} labels={labels} />
                </Grid.Col>
            </Grid>

            <CoverVersionPanel
                workspaceId={workspaceId}
                projectId={projectId}
                busyAction={versionState.busyAction}
                error={versionState.error || draftError}
                draftSavedAt={draftSavedAt}
                onSave={saveCandidate}
                canSave={hasCanvasContent}
                labels={labels}
            />
            <Text c="dimmed" size="xs">
                {t('steam_workshop.cover.local_draft_notice', {
                    defaultValue: '草稿仅保存在本机；保存候选版本后才会进入项目发布资产。',
                })}
            </Text>
        </Stack>
    );
};

export default ThumbnailGenerator;
