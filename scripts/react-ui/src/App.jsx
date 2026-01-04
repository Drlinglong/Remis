import React, { useState } from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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

import './App.css';

// Import pages...
import OriginalHomepage from './pages/HomePage';
import OriginalDocumentation from './pages/Documentation';
import OriginalInitialTranslation from './pages/InitialTranslation';
import OriginalProjectManagement from './pages/ProjectManagement';
import GlossaryManagerPage from './pages/GlossaryManagerPage';
import ProofreadingPage from './pages/ProofreadingPage';
import ToolsPage from './pages/ToolsPage';
import CICDPage from './pages/CICDPage';
import SettingsPage from './pages/SettingsPage';
import UnderDevelopmentPage from './pages/UnderDevelopmentPage';
import UnderConstructionPage from './pages/UnderConstructionPage';
import InConceptionPage from './pages/InConceptionPage';
import ArchivesPage from './pages/ArchivesPage';
import NeologismReviewPage from './pages/NeologismReviewPage';

// --- Single Source of Truth for Routing ---
const appRouteConfig = [
    { path: '/', element: <OriginalHomepage /> },
    { path: '/docs', element: <OriginalDocumentation /> },
    { path: '/translation', element: <OriginalInitialTranslation /> },
    { path: '/glossary-manager', element: <GlossaryManagerPage /> },
    { path: '/proofreading', element: <ProofreadingPage /> },
    { path: '/project-management', element: <OriginalProjectManagement /> },
    { path: '/project-management/:projectId', element: <OriginalProjectManagement /> },
    { path: '/neologism-review', element: <NeologismReviewPage /> },
    { path: '/archives', element: <ArchivesPage /> },
    { path: '/cicd', element: <CICDPage /> },
    { path: '/tools', element: <ToolsPage /> },
    { path: '/settings', element: <SettingsPage /> },
    { path: '/under-development', element: <UnderDevelopmentPage /> },
    { path: '/under-construction', element: <UnderConstructionPage /> },
    { path: '/in-conception', element: <InConceptionPage /> },
];

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
                                <Router>
                                    <TutorialProvider>
                                        <MainLayout>
                                            <Routes>
                                                {appRouteConfig.map(route => (
                                                    <Route key={route.path} path={route.path} element={route.element} />
                                                ))}
                                            </Routes>
                                        </MainLayout>
                                    </TutorialProvider>
                                </Router>
                            </TranslationProvider>
                        </SidebarProvider>
                    )}
                </NotificationProvider>
            </ThemeProvider>
        </ErrorBoundary>
    );
};

export default App;
