import React, { useEffect, useRef } from 'react';
import { Container, Stepper, Title, Modal, Stack, Text, Group, Button } from '@mantine/core';
import { IconRocket, IconSearch, IconSettings, IconChartBar } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useNotification } from '../context/NotificationContext';
import { getTutorialKey, useTutorial } from '../context/TutorialContext';
import useIncrementalTranslation from '../hooks/useIncrementalTranslation';
import ProjectSelectStep from '../components/incrementalTranslation/ProjectSelectStep';
import ConfigStep from '../components/incrementalTranslation/ConfigStep';
import PreScanResultsStep from '../components/incrementalTranslation/PreScanResultsStep';
import ExecutionStep from '../components/incrementalTranslation/ExecutionStep';
import styles from './Translation.module.css';

export const IncrementalTranslationPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    
    // Notification & Tutorial context
    const { notificationStyle } = useNotification();
    const { setPageContext, startTour } = useTutorial();

    // Refs for running logs viewport
    const logViewportRef = useRef(null);
    const logScrollRef = useRef(null);

    // Business Logic Custom Hook
    const state = useIncrementalTranslation(notificationStyle);

    // Sync Page Context for Tutorial Tour
    useEffect(() => {
        setPageContext((prev) => {
            const nextContext = `incremental-translation-step-${state.active}`;
            return prev === nextContext ? prev : nextContext;
        });
    }, [state.active, setPageContext]);

    // Handle prefilled project from React Router Navigation state
    useEffect(() => {
        const routedProjectId = location.state?.projectId;
        if (routedProjectId && state.projects.length > 0 && !state.selectedProject) {
            const matchedProject = state.projects.find((project) => project.project_id === routedProjectId);
            if (matchedProject) {
                state.handleSelectProject(matchedProject);
            }
        }
    }, [location.state, state.projects, state.selectedProject, state.handleSelectProject]);

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
                        projects={state.projects}
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
                        models={state.models}
                        customSourcePath={state.customSourcePath}
                        onSelectFolder={state.handleSelectFolder}
                        selectedLangs={state.selectedLangs}
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
                        apiProviders={state.apiProviders}

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
                        models={state.models}
                        batchSizeLimit={state.batchSizeLimit}
                        setBatchSizeLimit={state.setBatchSizeLimit}
                        concurrencyLimit={state.concurrencyLimit}
                        setConcurrencyLimit={state.setConcurrencyLimit}
                        rpmLimit={state.rpmLimit}
                        setRpmLimit={state.setRpmLimit}
                        customSourcePath={state.customSourcePath}
                        selectedProject={state.selectedProject}
                        selectedLangs={state.selectedLangs}
                        apiProviders={state.apiProviders}
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
