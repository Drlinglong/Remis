import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Paper,
  Progress,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconArrowRight, IconCheck, IconFolder, IconHistory } from '@tabler/icons-react';
import { useBeforeUnload, useBlocker, useNavigate } from 'react-router';
import { isTauri } from '@tauri-apps/api/core';
import layoutStyles from '../components/layout/Layout.module.css';
import { useTutorial } from '../context/TutorialContextCore';
import useProofreadingState from '../hooks/useProofreadingState';
import { usePersistentState } from '../hooks/usePersistentState';
import ProjectSelector from '../components/proofreading/ProjectSelector';
import { SourceFileSelector, AIFileSelector } from '../components/proofreading/ProofreadingFileList';
import ProofreadingWorkspace from '../components/proofreading/ProofreadingWorkspace';
import { taskDetailRoute } from '../utils/taskRoutes';

const ProofreadingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setPageContext } = useTutorial();
  const state = useProofreadingState();
  const { checkExternalRevision, fileInfo } = state;
  const [zoomLevel, setZoomLevel] = usePersistentState('proofread_zoom_level', '1');
  const [pendingAction, setPendingAction] = useState(null);
  const [closeRequested, setCloseRequested] = useState(false);
  const tauriWindowRef = useRef(null);
  const allowTauriCloseRef = useRef(false);
  const targetFiles = Object.values(state.targetFilesMap || {}).flat();
  const reviewedCount = targetFiles.filter((file) => file.status === 'done').length;
  const pendingFiles = targetFiles.filter((file) => file.status !== 'done');
  const nextPendingFile = pendingFiles.find(
    (file) => String(file.file_id) !== String(state.currentTargetFile?.file_id || ''),
  );
  const reviewProgress = targetFiles.length
    ? Math.round((reviewedCount / targetFiles.length) * 100)
    : 0;
  const originTaskId = state.originTaskId || state.searchParams?.get('taskId') || '';
  const translationRows = (state.rows || []).filter((row) => (
    row.row_type === 'translation' && row.key
  ));
  const focusedEntryKey = state.focusedEntryKey || state.focusEntryKey;
  const focusedEntryIndex = translationRows.findIndex((row) => row.key === focusedEntryKey);
  const nextEntry = translationRows[
    focusedEntryIndex >= 0 && focusedEntryIndex < translationRows.length - 1
      ? focusedEntryIndex + 1
      : 0
  ];

  useEffect(() => {
    setPageContext('proofreading');
  }, [setPageContext]);

  const blocker = useBlocker(useCallback(({ currentLocation, nextLocation }) => (
    state.isDirty
      && `${currentLocation.pathname}${currentLocation.search}` !== `${nextLocation.pathname}${nextLocation.search}`
  ), [state.isDirty]));

  useBeforeUnload(useCallback((event) => {
    if (!state.isDirty) return;
    event.preventDefault();
    event.returnValue = '';
  }, [state.isDirty]), { capture: true });

  useEffect(() => {
    if (!fileInfo) return undefined;
    const checkRevision = () => checkExternalRevision();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') checkRevision();
    };
    window.addEventListener('focus', checkRevision);
    document.addEventListener('visibilitychange', handleVisibility);
    const timer = window.setInterval(checkRevision, 15000);
    return () => {
      window.removeEventListener('focus', checkRevision);
      document.removeEventListener('visibilitychange', handleVisibility);
      window.clearInterval(timer);
    };
  }, [checkExternalRevision, fileInfo]);

  useEffect(() => {
    if (!isTauri()) return undefined;
    let disposed = false;
    let unlisten = null;
    import('@tauri-apps/api/window').then(({ getCurrentWindow }) => {
      const appWindow = getCurrentWindow();
      tauriWindowRef.current = appWindow;
      return appWindow.onCloseRequested((event) => {
        if (state.isDirty && !allowTauriCloseRef.current) {
          event.preventDefault();
          setCloseRequested(true);
        }
      });
    }).then((cleanup) => {
      if (disposed) cleanup();
      else unlisten = cleanup;
    }).catch((error) => {
      console.warn('Failed to attach Tauri close guard', error);
    });
    return () => {
      disposed = true;
      unlisten?.();
      tauriWindowRef.current = null;
    };
  }, [state.isDirty]);

  const closeTauriWindow = useCallback(async () => {
    if (!tauriWindowRef.current) return;
    allowTauriCloseRef.current = true;
    setCloseRequested(false);
    try {
      await tauriWindowRef.current.close();
    } catch (error) {
      allowTauriCloseRef.current = false;
      console.warn('Failed to close Tauri window', error);
    }
  }, []);

  const discardAndClose = useCallback(() => {
    state.discardCurrentDraft();
    closeTauriWindow();
  }, [closeTauriWindow, state]);

  const saveAndClose = useCallback(() => {
    setCloseRequested(false);
    state.requestSave(closeTauriWindow);
  }, [closeTauriWindow, state]);

  const requestProtectedAction = useCallback((action) => {
    if (state.isDirty) setPendingAction(() => action);
    else action();
  }, [state.isDirty]);

  const completeCurrentAndContinue = useCallback(() => {
    state.requestSave(async () => {
      const updated = await state.markCurrentFileDone();
      if (!updated) return;
      if (nextPendingFile && state.selectedProject?.project_id) {
        state.setSearchParams({
          projectId: state.selectedProject.project_id,
          fileId: nextPendingFile.file_id,
        });
      }
    });
  }, [nextPendingFile, state]);

  const saveAndNextEntry = useCallback(() => {
    if (!nextEntry?.key) return;
    state.requestSave(() => state.requestFocusEntry(nextEntry.key));
  }, [nextEntry?.key, state]);

  const completePendingLeave = useCallback(() => {
    const action = pendingAction;
    setPendingAction(null);
    if (blocker.state === 'blocked') blocker.proceed();
    else action?.();
  }, [blocker, pendingAction]);

  const cancelPendingLeave = useCallback(() => {
    setPendingAction(null);
    if (blocker.state === 'blocked') blocker.reset();
  }, [blocker]);

  const discardAndLeave = useCallback(() => {
    state.discardCurrentDraft();
    completePendingLeave();
  }, [completePendingLeave, state]);

  const saveAndLeave = useCallback(() => {
    state.requestSave(completePendingLeave);
  }, [completePendingLeave, state]);

  const keepDraftAndLeave = useCallback(() => {
    state.persistSessionNow();
    completePendingLeave();
  }, [completePendingLeave, state]);

  const sourceFileSelector = (
    <SourceFileSelector
      sourceFiles={state.sourceFiles}
      currentSourceFile={state.currentSourceFile}
      onSourceFileChange={(value) => requestProtectedAction(() => state.handleSourceFileChange(value))}
    />
  );

  const aiFileSelector = (
    <AIFileSelector
      sourceFiles={state.sourceFiles}
      currentSourceFile={state.currentSourceFile}
      targetFilesMap={state.targetFilesMap}
      currentTargetFile={state.currentTargetFile}
      onTargetFileChange={(value) => requestProtectedAction(() => state.handleTargetFileChange(value))}
    />
  );

  return (
    <div style={{ height: 'calc(100vh - 20px)', display: 'flex', flexDirection: 'column', padding: '10px', width: '100%', minHeight: 0 }}>
      <Paper withBorder p="sm" radius="md" className={layoutStyles.glassCard} style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <Group justify="space-between" mb="sm" w="100%" wrap="wrap">
          <Group wrap="wrap">
            <Title order={3}>{t('page_title_proofreading')}</Title>
            <Box id="proofreading-mod-select">
              <ProjectSelector
                projects={state.projects}
                selectedProject={state.selectedProject}
                onProjectSelect={(value) => requestProtectedAction(() => state.handleProjectSelect(value))}
              />
            </Box>
          </Group>

          <Group gap="sm">
            {originTaskId && (
              <Button
                variant="light"
                size="sm"
                leftSection={<IconHistory size={16} />}
                onClick={() => requestProtectedAction(() => navigate(taskDetailRoute(originTaskId)))}
              >
                {t('proofreading.return_to_task', { defaultValue: 'Return to source task' })}
              </Button>
            )}
            <Text size="sm" c="dimmed" mr={4}>{t('proofreading.scale')}:</Text>
            <Select
              value={zoomLevel}
              onChange={setZoomLevel}
              data={[
                { value: '1', label: '100%' },
                { value: '1.1', label: '110%' },
                { value: '1.25', label: '125%' },
                { value: '1.5', label: '150%' },
                { value: '1.75', label: '175%' },
                { value: '2', label: '200%' },
              ]}
              size="sm"
              variant="filled"
              style={{ width: 88 }}
              styles={{ input: { paddingRight: 0, textAlign: 'center' } }}
            />
            <Button
              variant="default"
              size="sm"
              leftSection={<IconFolder size={16} />}
              onClick={state.handleOpenFolder}
              disabled={!state.fileInfo}
            >
              {t('proofreading.open_folder')}
            </Button>
          </Group>
        </Group>

        {state.selectedProject && targetFiles.length > 0 && (
          <Paper withBorder p="xs" mb="sm" radius="md" data-testid="proofreading-progress">
            <Group justify="space-between" align="center" wrap="wrap">
              <Box style={{ flex: 1, minWidth: 220 }}>
                <Group justify="space-between" gap="sm" mb={4}>
                  <Text size="sm" fw={700}>
                    {t('project_management.file_list.table.progress')}
                  </Text>
                  <Badge color={pendingFiles.length ? 'blue' : 'teal'} variant="light">
                    {reviewedCount}/{targetFiles.length}
                  </Badge>
                </Group>
                <Progress value={reviewProgress} size="sm" radius="xl" />
              </Box>
              {pendingFiles.length > 0 ? (
                <Button
                  size="sm"
                  color="teal"
                  leftSection={<IconCheck size={16} />}
                  rightSection={nextPendingFile ? <IconArrowRight size={16} /> : null}
                  onClick={completeCurrentAndContinue}
                  loading={state.saving}
                  disabled={!state.currentTargetFile}
                >
                  {nextPendingFile
                    ? t('glossary_health_save_and_next')
                    : t('project_management.file_status.done')}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="light"
                  color="teal"
                  rightSection={<IconArrowRight size={16} />}
                  onClick={() => navigate(
                    `/project-management/${encodeURIComponent(state.selectedProject.project_id)}`,
                  )}
                >
                  {t('page_title_project_management')}
                </Button>
              )}
            </Group>
          </Paper>
        )}

        <div id="proofreading-main-content" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', zoom: zoomLevel }}>
          <ProofreadingWorkspace
            rows={state.rows}
            onFinalValueChange={state.updateRowFinalValue}
            validationResults={state.validationResults}
            stats={state.stats}
            loading={state.loading}
            validating={state.validating}
            saving={state.saving}
            isDirty={state.isDirty}
            translationChangeCount={state.translationChangeCount}
            commentChangeCount={state.commentChangeCount}
            saveModalOpen={state.saveModalOpen}
            variableWarnings={state.variableWarnings}
            onValidate={state.handleValidate}
            onSave={() => state.requestSave()}
            onSaveAndNext={saveAndNextEntry}
            canSaveAndNext={Boolean(nextEntry)}
            onConfirmSave={() => state.confirmSave(true)}
            onDiscardCommentChanges={() => state.confirmSave(false)}
            onCancelSave={state.cancelSave}
            sourceFileSelector={sourceFileSelector}
            aiFileSelector={aiFileSelector}
            query={state.query}
            onQueryChange={state.setQuery}
            filter={state.filter}
            onFilterChange={state.setFilter}
            focusEntryKey={state.focusEntryKey}
            initialScrollOffset={state.scrollOffset}
            onScrollOffsetChange={state.setScrollOffset}
            onFocusedEntryChange={state.setFocusedEntryKey}
            onRequestFocusEntry={state.requestFocusEntry}
            draftRestoreStatus={state.draftRestoreStatus}
            draftConflict={state.draftConflict}
            onDismissDraftConflict={state.dismissDraftConflict}
            externalChangeDetected={state.externalChangeDetected}
            onReloadFromDisk={() => state.loadEditorData(
              state.fileInfo.project_id,
              state.fileInfo.file_id,
            )}
          />
        </div>
      </Paper>

      <Modal
        opened={Boolean(pendingAction) || blocker.state === 'blocked'}
        onClose={cancelPendingLeave}
        title={t('proofreading.unsaved_title', { defaultValue: 'Unsaved proofreading changes' })}
        centered
        closeOnClickOutside={false}
      >
        <Stack>
          <Alert color="orange">
            {t('proofreading.unsaved_body', {
              defaultValue: 'Save your changes, keep editing, or explicitly discard them before leaving.',
            })}
          </Alert>
          <Group justify="flex-end">
            <Button variant="default" onClick={cancelPendingLeave}>
              {t('proofreading.continue_editing', { defaultValue: 'Continue editing' })}
            </Button>
            <Button variant="light" color="red" onClick={discardAndLeave}>
              {t('proofreading.discard_and_leave', { defaultValue: 'Discard and leave' })}
            </Button>
            {blocker.state === 'blocked' && !pendingAction && (
              <Button variant="light" onClick={keepDraftAndLeave}>
                {t('proofreading.keep_draft_and_leave', { defaultValue: 'Keep draft and leave' })}
              </Button>
            )}
            <Button onClick={saveAndLeave}>
              {t('proofreading.save_and_leave', { defaultValue: 'Save and leave' })}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={closeRequested}
        onClose={() => setCloseRequested(false)}
        title={t('proofreading.close_unsaved_title', { defaultValue: 'Close with unsaved changes?' })}
        centered
        closeOnClickOutside={false}
      >
        <Stack>
          <Alert color="orange">
            {t('proofreading.close_unsaved_body', {
              defaultValue: 'Your proofreading changes have not been saved. Save them, discard them, or return to editing.',
            })}
          </Alert>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCloseRequested(false)}>
              {t('proofreading.continue_editing', { defaultValue: 'Continue editing' })}
            </Button>
            <Button variant="light" color="red" onClick={discardAndClose}>
              {t('proofreading.discard_and_close', { defaultValue: 'Discard and close' })}
            </Button>
            <Button onClick={saveAndClose}>
              {t('proofreading.save_and_close', { defaultValue: 'Save and close' })}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  );
};

export default ProofreadingPage;
