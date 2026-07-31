import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Grid, Paper, Stack, Text } from '@mantine/core';
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

const translationLabels = (t) => ({
    toolboxTitle: t('thumbnail_generator.toolbox_title'),
    uploadModImage: t('thumbnail_generator.upload_mod_image'),
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

const downloadDataUrl = (dataUrl) => {
    const link = document.createElement('a');
    link.download = 'thumbnail.png';
    link.href = dataUrl;
    link.click();
};

const waitForPaint = () => new Promise((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
});

const ThumbnailGenerator = ({
    projectId = null,
    workspaceId = null,
    currentCoverVersionId = null,
}) => {
    const { t } = useTranslation();
    const labels = translationLabels(t);
    const canvasContainerRef = useRef(null);
    const editor = useCoverEditor({ defaultText: t('thumbnail_generator.default_text') });
    const { replaceCanvas, selectedId, setSelectedId } = editor;
    const { draftSavedAt, draftError } = useCoverDraft({
        workspaceId,
        projectId,
        canvasState: editor.canvasState,
        replaceCanvas: editor.replaceCanvas,
    });

    const loadCanvas = useCallback(async (canvas) => {
        replaceCanvas(await hydrateCoverCanvas(canvas));
    }, [replaceCanvas]);
    const versionState = useCoverVersions({
        workspaceId,
        currentVersionId: currentCoverVersionId,
        onLoadCanvas: loadCanvas,
    });

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
    const handleDownload = async () => downloadDataUrl(await capturePng());
    const handleDrop = (event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file?.type.startsWith('image/')) editor.addFileImage(file, 'mod');
    };
    const hasCanvasContent = editor.backgroundColor !== '#ffffff'
        || Boolean(editor.backgroundImage)
        || editor.elements.length > 0;

    return (
        <Stack data-remis-surface="canvas" className="cover-editor-workspace">
            <Grid align="flex-start">
                <Grid.Col span={{ base: 12, md: 3 }}>
                    <CoverToolbox editor={editor} labels={labels} />
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }} className="cover-editor-center">
                    <Paper withBorder p="md" data-remis-surface="surface" className="cover-canvas-panel">
                        <CoverCanvas
                            canvasRef={canvasContainerRef}
                            editor={editor}
                            onDrop={handleDrop}
                            onDragOver={(event) => event.preventDefault()}
                            onRequestBackground={() => editor.inputRefs.backgroundInputRef.current?.click()}
                            placeholder={labels.placeholder}
                            dragHint={labels.dragHint}
                        />
                        <Button variant="light" onClick={handleDownload} disabled={!hasCanvasContent}>
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
                versions={versionState.versions}
                selectedVersionId={versionState.selectedVersionId}
                busyAction={versionState.busyAction}
                error={versionState.error || draftError}
                draftSavedAt={draftSavedAt}
                onSave={saveCandidate}
                onLoad={versionState.loadVersion}
                onSelect={versionState.selectVersion}
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
