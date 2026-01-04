import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Paper,
  Title,
  Button,
  Group,
  Select,
  Tabs,
  Text,
  Box
} from '@mantine/core';
import {
  IconFolder,
  IconFileText,
  IconEdit
} from '@tabler/icons-react';
import layoutStyles from '../components/layout/Layout.module.css';
import { useTutorial } from '../context/TutorialContext';
import useProofreadingState from '../hooks/useProofreadingState';
import { usePersistentState } from '../hooks/usePersistentState';
import ProjectSelector from '../components/proofreading/ProjectSelector';
import { SourceFileSelector, AIFileSelector } from '../components/proofreading/ProofreadingFileList';
import ProofreadingWorkspace from '../components/proofreading/ProofreadingWorkspace';
import FreeLinterMode from '../components/proofreading/FreeLinterMode';

/**
 * 校对页面主组件
 * 轻量级容器，仅负责布局和组件组合
 */
const ProofreadingPage = () => {
  const { t } = useTranslation();
  const { setPageContext } = useTutorial();
  const state = useProofreadingState();

  // 本地 UI 状态
  const [activeTab, setActiveTab] = usePersistentState('proofread_active_tab', 'file');
  const [zoomLevel, setZoomLevel] = usePersistentState('proofread_zoom_level', '1');

  useEffect(() => {
    setPageContext('proofreading');
  }, [setPageContext]);

  // 源文件选择器组件
  const sourceFileSelector = (
    <SourceFileSelector
      sourceFiles={state.sourceFiles}
      currentSourceFile={state.currentSourceFile}
      onSourceFileChange={state.handleSourceFileChange}
    />
  );

  // AI 初稿选择器组件
  const aiFileSelector = (
    <AIFileSelector
      sourceFiles={state.sourceFiles}
      currentSourceFile={state.currentSourceFile}
      targetFilesMap={state.targetFilesMap}
      currentTargetFile={state.currentTargetFile}
      onTargetFileChange={state.handleTargetFileChange}
    />
  );

  return (
    <div style={{ height: 'calc(100vh - 20px)', display: 'flex', flexDirection: 'column', padding: '10px', width: '100%' }}>
      <Paper withBorder p="xs" radius="md" className={layoutStyles.glassCard} style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%', overflow: 'hidden' }}>

        {/* Header */}
        <Group justify="space-between" mb="xs" w="100%">
          <Group>
            <Title order={4}>{t('page_title_proofreading')}</Title>
            <Box id="proofreading-mod-select">
              <ProjectSelector
                projects={state.projects}
                selectedProject={state.selectedProject}
                onProjectSelect={state.handleProjectSelect}
              />
            </Box>
          </Group>

          <Group>

            <Group gap="xs">
              <Text size="xs" c="dimmed" mr={4}>{t('common.page_scale', 'Scale')}:</Text>
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
                size="xs"
                variant="filled"
                style={{ width: 75 }}
                styles={{ input: { paddingRight: 0, textAlign: 'center' } }}
              />
              <Button
                variant="default"
                size="xs"
                leftSection={<IconFolder size={14} />}
                onClick={state.handleOpenFolder}
              >
                {t('proofreading.open_folder')}
              </Button>
            </Group>
          </Group>
        </Group>

        {/* Main Content */}
        <div id="proofreading-main-content" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', zoom: zoomLevel }}>
          <ProofreadingWorkspace
            originalContentStr={state.originalContentStr}
            aiContentStr={state.aiContentStr}
            finalContentStr={state.finalContentStr}
            onFinalContentChange={state.setFinalContentStr}
            originalEditorRef={state.originalEditorRef}
            aiEditorRef={state.aiEditorRef}
            finalEditorRef={state.finalEditorRef}
            validationResults={state.validationResults}
            stats={state.stats}
            loading={state.loading}
            saving={state.saving}
            keyChangeWarning={state.keyChangeWarning}
            saveModalOpen={state.saveModalOpen}
            onValidate={state.handleValidate}
            onSave={state.handleSaveClick}
            onConfirmSave={state.confirmSave}
            onCancelSave={() => state.setSaveModalOpen(false)}
            fileInfo={state.fileInfo}
            onOpenFolder={state.handleOpenFolder}
            sourceFileSelector={sourceFileSelector}
            aiFileSelector={aiFileSelector}
          />
        </div>
      </Paper>
    </div>
  );
};

export default ProofreadingPage;
