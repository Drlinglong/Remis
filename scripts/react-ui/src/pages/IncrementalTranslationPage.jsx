import React, { useEffect, useRef } from 'react';
import { Container, Stepper, Title, Modal, Stack, Text, Group, Button } from '@mantine/core';
import { IconRocket, IconSearch, IconSettings, IconChartBar } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useNotification } from '../context/NotificationContextCore';
import { getTutorialKey, useTutorial } from '../context/TutorialContextCore';
import useIncrementalTranslation from '../hooks/useIncrementalTranslation';
import ProjectSelectStep from '../components/incrementalTranslation/ProjectSelectStep';
import ConfigStep from '../components/incrementalTranslation/ConfigStep';
import PreScanResultsStep from '../components/incrementalTranslation/PreScanResultsStep';
import ExecutionStep from '../components/incrementalTranslation/ExecutionStep';
import styles from './Translation.module.css';
import { useRemisCopilotContext } from '../context/CopilotContext';
import { useCopilotStallReminder } from '../hooks/useCopilotStallReminder';
import { sanitizeCopilotLogLine } from '../services/copilotPageContext';
import { buildProofreadingUrl } from '../utils/proofreadingLinks';
import { taskDetailRoute } from '../utils/taskRoutes';

const EMPTY_ARRAY = [];

export const IncrementalTranslationPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    
    // Notification & Tutorial context
    const { notificationStyle } = useNotification();
    const { setPageContext, startTour } = useTutorial();
    const { registerPageContext } = useRemisCopilotContext();

    // Refs for running logs viewport
    const logViewportRef = useRef(null);
    const logScrollRef = useRef(null);

    // Business Logic Custom Hook
    const state = useIncrementalTranslation(notificationStyle);
    const safeProjects = Array.isArray(state.projects) ? state.projects : EMPTY_ARRAY;
    const safeModels = Array.isArray(state.models) ? state.models : EMPTY_ARRAY;
    const safeApiProviders = Array.isArray(state.apiProviders) ? state.apiProviders : EMPTY_ARRAY;
    const safeSelectedLangs = Array.isArray(state.selectedLangs) ? state.selectedLangs : EMPTY_ARRAY;
    const {
        active,
        selectedProject,
    } = state;

    const contextSignature = JSON.stringify({
        active,
        projectId: selectedProject?.project_id || null,
        provider: state.selectedProvider,
        model: state.selectedModel,
        langs: safeSelectedLangs,
        loading: state.loading,
        executing: state.executing,
        progress: state.progress,
        scanReady: Boolean(state.scanResults),
        completed: Boolean(state.finalSummary),
    });
    const reminder = useCopilotStallReminder({
        enabled: !state.loading && !state.executing && !state.finalSummary,
        meaningfulState: contextSignature,
        error: state.error || state.errorKey,
        blocked: active > 0 && !selectedProject,
        openingMessage: t(
            'copilot.incremental_local_prompt',
            '看起来你在增量更新流程中遇到了一些问题。你可以问我“下一步该做什么”，我会结合当前步骤说明。',
        ),
    });

    useEffect(() => {
        const stepNames = ['select_project', 'configure', 'review_scan', 'execution'];
        registerPageContext({
            pageId: 'incremental-translation',
            pageTitle: t('incremental_translation.title'),
            stepId: stepNames[active] || 'execution',
            stepIndex: active,
            stepCount: 4,
            project: selectedProject ? {
                id: selectedProject.project_id,
                name: selectedProject.name || selectedProject.project_name || '',
                gameId: selectedProject.game_id || '',
            } : null,
            status: {
                loading: state.loading,
                executing: state.executing,
                progress: state.progress,
                hasScanResults: Boolean(state.scanResults),
                completed: Boolean(state.finalSummary),
                error: state.errorKey || (state.error ? String(state.error) : null),
            },
            configuration: {
                provider: state.selectedProvider || null,
                model: state.selectedModel || null,
                targetLanguages: safeSelectedLangs,
            },
            recentLogs: (state.logs || []).slice(-12).map((line) => sanitizeCopilotLogLine(line)),
            reminder,
        });
        return () => registerPageContext(null);
    }, [active, registerPageContext, reminder, safeSelectedLangs, selectedProject, state.error, state.errorKey,
        state.executing, state.finalSummary, state.loading, state.logs, state.progress, state.scanResults,
        state.selectedModel, state.selectedProvider, t]);

    // Sync Page Context for Tutorial Tour
    useEffect(() => {
        setPageContext((prev) => {
            const nextContext = `incremental-translation-step-${active}`;
            return prev === nextContext ? prev : nextContext;
        });
    }, [active, setPageContext]);

    const handleFinish = () => {
        state.resetPersistedState();
        navigate('/project-management');
    };

    return (
        <Container size="xl" py="xl" className={styles.incrementalPage}>
            <Title order={2} mb="xl" className={styles.pageTitle}>
                <IconRocket size={32} style={{ marginRight: 12, verticalAlign: 'middle' }} />
                {t('incremental_translation.title')}
            </Title>

            <Stepper active={state.active} onStepClick={state.setActive} allowNextStepsSelect={false} breakpoint="sm">
                {/* --- Step 1: Select Project --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_1_title')}
                    description={t('incremental_translation.step_1_desc')}
                    icon={<IconSearch size={18} />}
                >
                    <ProjectSelectStep
                        projects={safeProjects}
                        searchQuery={state.searchQuery}
                        setSearchQuery={state.setSearchQuery}
                        gameFilter={state.gameFilter}
                        setGameFilter={state.setGameFilter}
                        selectedProject={state.selectedProject}
                        onSelectProject={state.handleSelectProject}
                    />
                </Stepper.Step>

                {/* --- Step 2: Validation & Setup --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_2_title')}
                    description={t('incremental_translation.step_2_desc')}
                    icon={<IconSettings size={18} />}
                >
                    <ConfigStep
                        loading={state.loading}
                        error={state.error}
                        errorKey={state.errorKey}
                        archiveInfo={state.archiveInfo}
                        selectedProject={state.selectedProject}
                        checkpointFound={state.checkpointFound}
                        checkpointInfo={state.checkpointInfo}
                        useResume={state.useResume}
                        setUseResume={state.setUseResume}
                        showResumeDetails={state.showResumeDetails}
                        setShowResumeDetails={state.setShowResumeDetails}
                        selectedProvider={state.selectedProvider}
                        handleProviderChange={state.handleProviderChange}
                        selectedModel={state.selectedModel}
                        setSelectedModel={state.setSelectedModel}
                        models={safeModels}
                        customSourcePath={state.customSourcePath}
                        onSelectFolder={state.handleSelectFolder}
                        selectedLangs={safeSelectedLangs}
                        setSelectedLangs={state.setSelectedLangs}
                        batchSizeLimit={state.batchSizeLimit}
                        setBatchSizeLimit={state.setBatchSizeLimit}
                        concurrencyLimit={state.concurrencyLimit}
                        setConcurrencyLimit={state.setConcurrencyLimit}
                        rpmLimit={state.rpmLimit}
                        setRpmLimit={state.setRpmLimit}
                        
                        // Embedded Workshop Configuration
                        embeddedWorkshopEnabled={state.embeddedWorkshopEnabled}
                        setEmbeddedWorkshopEnabled={state.setEmbeddedWorkshopEnabled}
                        embeddedWorkshopFollowPrimary={state.embeddedWorkshopFollowPrimary}
                        setEmbeddedWorkshopFollowPrimary={state.setEmbeddedWorkshopFollowPrimary}
                        embeddedWorkshopProvider={state.embeddedWorkshopProvider}
                        setEmbeddedWorkshopProvider={state.setEmbeddedWorkshopProvider}
                        embeddedWorkshopModel={state.embeddedWorkshopModel}
                        setEmbeddedWorkshopModel={state.setEmbeddedWorkshopModel}
                        embeddedWorkshopBatchSize={state.embeddedWorkshopBatchSize}
                        setEmbeddedWorkshopBatchSize={state.setEmbeddedWorkshopBatchSize}
                        embeddedWorkshopConcurrency={state.embeddedWorkshopConcurrency}
                        setEmbeddedWorkshopConcurrency={state.setEmbeddedWorkshopConcurrency}
                        embeddedWorkshopRpm={state.embeddedWorkshopRpm}
                        setEmbeddedWorkshopRpm={state.setEmbeddedWorkshopRpm}
                        showWorkshopSettings={state.showWorkshopSettings}
                        setShowWorkshopSettings={state.setShowWorkshopSettings}
                        apiProviders={safeApiProviders}

                        // Actions
                        runPreScan={state.runPreScan}
                        onBack={() => state.setActive(0)}
                    />
                </Stepper.Step>

                {/* --- Step 3: Pre-scan Results --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_3_title')}
                    description={t('incremental_translation.step_3_desc')}
                    icon={<IconChartBar size={18} />}
                >
                    <PreScanResultsStep
                        scanResults={state.scanResults}
                        selectedProvider={state.selectedProvider}
                        handleProviderChange={state.handleProviderChange}
                        selectedModel={state.selectedModel}
                        setSelectedModel={state.setSelectedModel}
                        models={safeModels}
                        batchSizeLimit={state.batchSizeLimit}
                        setBatchSizeLimit={state.setBatchSizeLimit}
                        concurrencyLimit={state.concurrencyLimit}
                        setConcurrencyLimit={state.setConcurrencyLimit}
                        rpmLimit={state.rpmLimit}
                        setRpmLimit={state.setRpmLimit}
                        customSourcePath={state.customSourcePath}
                        selectedProject={state.selectedProject}
                        selectedLangs={safeSelectedLangs}
                        apiProviders={safeApiProviders}
                        archiveInfo={state.archiveInfo}
                        startTranslation={state.startTranslation}
                        onBack={() => state.setActive(1)}
                        loading={state.loading}
                        executing={state.executing}
                    />
                </Stepper.Step>

                {/* --- Step 4: Execution --- */}
                <Stepper.Completed>
                    <ExecutionStep
                        progress={state.progress}
                        executing={state.executing}
                        progressInfo={state.progressInfo}
                        logs={state.logs}
                        finalSummary={state.finalSummary}
                        logViewportRef={logViewportRef}
                        logScrollRef={logScrollRef}
                        openOutputFolder={state.openOutputFolder}
                        handleFinish={handleFinish}
                        completionSource={state.completionSource}
                        onViewTask={state.currentTaskId
                            ? () => navigate(taskDetailRoute(state.currentTaskId))
                            : null}
                        onStartProofreading={state.selectedProject?.project_id
                            ? () => navigate(buildProofreadingUrl({
                                projectId: state.selectedProject.project_id,
                            }))
                            : null}
                    />
                </Stepper.Completed>
            </Stepper>

            {/* --- Tutorial Prompt Modal --- */}
            <Modal
                opened={state.showTutorialPrompt}
                onClose={() => {
                    state.setShowTutorialPrompt(false);
                    localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                }}
                title={t('tutorial.auto_start_prompt.title')}
                centered
                radius="md"
            >
                <Stack>
                    <Text size="sm">{t('tutorial.auto_start_prompt.message')}</Text>
                    <Group justify="flex-end" mt="md">
                        <Button
                            variant="subtle"
                            color="gray"
                            onClick={() => {
                                state.setShowTutorialPrompt(false);
                                localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                            }}
                        >
                            {t('tutorial.auto_start_prompt.cancel')}
                        </Button>
                        <Button
                            color="blue"
                            onClick={() => {
                                state.setShowTutorialPrompt(false);
                                localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                                startTour();
                            }}
                        >
                            {t('tutorial.auto_start_prompt.confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </Container>
    );
};

export default IncrementalTranslationPage;
