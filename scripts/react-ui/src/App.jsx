import React, { Suspense, lazy, useState } from 'react';
import { createHashRouter, Outlet, RouterProvider } from 'react-router-dom';
import { Center, Loader } from '@mantine/core';

// import { MantineProvider } from '@mantine/core'; // Removed unused import
import '@mantine/core/styles.css';

import { ThemeProvider } from './ThemeContext';
import GlobalStyles from './components/GlobalStyles';
import { NotificationProvider } from './context/NotificationContext';
import { SidebarProvider } from './context/SidebarContext';
import { TranslationProvider } from './context/TranslationContext';
import { TutorialProvider } from './context/TutorialContext';
import { MainLayout } from './components/layout/MainLayout';
import SplashScreen from './components/SplashScreen';
import ErrorBoundary from './components/ErrorBoundary';
import ProjectWatchScheduler from './components/ProjectWatchScheduler';
import { FEATURES } from './config/features';
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

const RouteFallback = () => (
    <Center h="50vh">
        <Loader size="lg" type="dots" />
    </Center>
);

// --- Single Source of Truth for Routing ---
const appRouteConfig = [
    { path: '/', element: <HomePage /> },
    { path: '/docs', element: <DocumentationPage /> },
    { path: '/translation', element: <InitialTranslationPage /> },
    { path: '/glossary-manager', element: <GlossaryManagerPage /> },
    { path: '/proofreading', element: <ProofreadingPage /> },
    { path: '/project-management', element: <ProjectManagementPage /> },
    { path: '/project-management/:projectId', element: <ProjectManagementPage /> },
    { path: '/project-tracking', element: <ProjectTrackingPage /> },
    { path: '/incremental-translation', element: <IncrementalTranslationPage /> },
    ...(FEATURES.ENABLE_NEOLOGISM_TRIBUNAL ? [{ path: '/neologism-review', element: <NeologismReviewPage /> }] : []),
    { path: '/archives', element: <ArchivesPage /> },
    { path: '/agent-workshop', element: <AgentWorkshopPage /> },
    ...(FEATURES.ENABLE_REMIS_COPILOT ? [{ path: '/copilot', element: <CopilotPage /> }] : []),
    { path: '/cicd', element: <CICDPage /> },
    { path: '/tools', element: <ToolsPage /> },
    { path: '/settings', element: <SettingsPage /> },
    { path: '/under-development', element: <UnderDevelopmentPage /> },
    { path: '/under-construction', element: <UnderConstructionPage /> },
    { path: '/in-conception', element: <InConceptionPage /> },
];

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
                                <RouterProvider router={appRouter} fallbackElement={<RouteFallback />} />
                            </TranslationProvider>
                        </SidebarProvider>
                    )}
                </NotificationProvider>
            </ThemeProvider>
        </ErrorBoundary>
    );
};

export default App;
