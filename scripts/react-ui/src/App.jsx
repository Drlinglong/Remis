import React, { Suspense, lazy, useState } from 'react';
import { createHashRouter, Outlet } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { Center, Loader } from '@mantine/core';

// import { MantineProvider } from '@mantine/core'; // Removed unused import
import '@mantine/core/styles.css';

import { ThemeProvider } from './ThemeContext';
import GlobalStyles from './components/GlobalStyles';
import { NotificationProvider } from './context/NotificationContext';
import { SidebarProvider } from './context/SidebarContext';
import { TranslationProvider } from './context/TranslationContext';
import { TaskCenterProvider } from './context/TaskCenterContext';
import { TutorialProvider } from './context/TutorialContext';
import { MainLayout } from './components/layout/MainLayout';
import SplashScreen from './components/SplashScreen';
import ErrorBoundary from './components/ErrorBoundary';
import ProjectWatchScheduler from './components/ProjectWatchScheduler';
import { FEATURES } from './config/features';
import { buildAppRouteConfig } from './config/pageRegistry';
import { CopilotContextProvider } from './context/CopilotContext';
import CopilotFloatingWidget from './components/copilot/CopilotFloatingWidget';

import './App.css';

const HomePage = lazy(() => import('./pages/HomePage'));
const DocumentationPage = lazy(() => import('./pages/Documentation'));
const InitialTranslationPage = lazy(() => import('./pages/InitialTranslation'));
const ProjectManagementPage = lazy(() => import('./pages/ProjectManagement'));
const ProjectTrackingPage = lazy(() => import('./pages/ProjectTrackingPage'));
const GlossaryManagerPage = lazy(() => import('./pages/GlossaryManagerPage'));
const ProofreadingPage = lazy(() => import('./pages/ProofreadingPage'));
const ToolsPage = lazy(() => import('./pages/ToolsPage'));
const CICDPage = lazy(() => import('./pages/CICDPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const IncrementalTranslationPage = lazy(() => import('./pages/IncrementalTranslationPage'));
const UnderDevelopmentPage = lazy(() => import('./pages/UnderDevelopmentPage'));
const UnderConstructionPage = lazy(() => import('./pages/UnderConstructionPage'));
const InConceptionPage = lazy(() => import('./pages/InConceptionPage'));
const ArchivesPage = lazy(() => import('./pages/ArchivesPage'));
const NeologismReviewPage = lazy(() => import('./pages/NeologismReviewPage'));
const AgentWorkshopPage = lazy(() => import('./pages/AgentWorkshopPage'));
const CopilotPage = lazy(() => import('./pages/CopilotPage'));
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'));
const TaskHistoryPage = lazy(() => import('./pages/TaskHistoryPage'));
const GlossaryHealthReviewPage = lazy(() => import('./pages/GlossaryHealthReviewPage'));
const ModelArenaPage = lazy(() => import('./pages/ModelArenaPage'));

const RouteFallback = () => (
    <Center h="50vh">
        <Loader size="lg" type="dots" />
    </Center>
);

const pageElements = {
    home: <HomePage />,
    documentation: <DocumentationPage />,
    'initial-translation': <InitialTranslationPage />,
    'glossary-manager': <GlossaryManagerPage />,
    proofreading: <ProofreadingPage />,
    'project-management': <ProjectManagementPage />,
    'task-detail': <TaskDetailPage />,
    'glossary-health-review': <GlossaryHealthReviewPage />,
    'task-history': <TaskHistoryPage />,
    'project-tracking': <ProjectTrackingPage />,
    'incremental-translation': <IncrementalTranslationPage />,
    'model-arena': <ModelArenaPage />,
    'neologism-review': <NeologismReviewPage />,
    archives: <ArchivesPage />,
    'agent-workshop': <AgentWorkshopPage />,
    copilot: <CopilotPage />,
    cicd: <CICDPage />,
    tools: <ToolsPage />,
    settings: <SettingsPage />,
    'under-development': <UnderDevelopmentPage />,
    'under-construction': <UnderConstructionPage />,
    'in-conception': <InConceptionPage />,
};

const appRouteConfig = buildAppRouteConfig(pageElements, FEATURES);

const AppRouterLayout = () => (
    <TutorialProvider>
        <CopilotContextProvider>
            <MainLayout>
                <ProjectWatchScheduler />
                <Suspense fallback={<RouteFallback />}>
                    <Outlet />
                </Suspense>
                {FEATURES.ENABLE_REMIS_COPILOT && <CopilotFloatingWidget />}
            </MainLayout>
        </CopilotContextProvider>
    </TutorialProvider>
);

const appRouter = createHashRouter([
    {
        element: <AppRouterLayout />,
        children: appRouteConfig,
    },
]);

const App = () => {
    const [isReady, setIsReady] = useState(false);

    return (
        <ErrorBoundary>
            <ThemeProvider>
                <GlobalStyles />
                <NotificationProvider>
                    {!isReady ? (
                        <SplashScreen onReady={() => setIsReady(true)} />
                    ) : (
                        <SidebarProvider>
                            <TranslationProvider>
                                <TaskCenterProvider>
                                    <RouterProvider router={appRouter} fallbackElement={<RouteFallback />} />
                                </TaskCenterProvider>
                            </TranslationProvider>
                        </SidebarProvider>
                    )}
                </NotificationProvider>
            </ThemeProvider>
        </ErrorBoundary>
    );
};

export default App;
