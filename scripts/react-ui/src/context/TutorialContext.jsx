import React, { useState, useEffect, useCallback } from 'react';
import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import { useTranslation } from 'react-i18next';
import { getTutorialSteps } from '../config/tutorialSteps';
import { TutorialContext } from './TutorialContextCore';

export const TutorialProvider = ({ children }) => {
    const { t } = useTranslation();
    const [isTourActive, setIsTourActive] = useState(false);
    const [pageContext, setPageContext] = useState('home'); // Default page context

    const startTour = useCallback((pageName = null) => {
        // Use provided pageName or fallback to current pageContext
        const targetPage = pageName || pageContext;
        const steps = getTutorialSteps(t, targetPage);

        if (!steps || steps.length === 0) {
            console.warn(`No tutorial steps found for page: ${targetPage}`);
            return;
        }

        const driverObj = driver({
            showProgress: true,
            animate: true,
            overlayOpacity: 0.7,
            stagePadding: 4,
            nextBtnText: t('tutorial.next'),
            prevBtnText: t('tutorial.prev'),
            doneBtnText: t('tutorial.done'),
            onDeselected: () => {
                setIsTourActive(false);
            },
            onDestroyed: () => {
                setIsTourActive(false);
            },
            steps: steps
        });

        setIsTourActive(true);
        driverObj.drive();
    }, [t, pageContext]);

    // Optional: Check for first-time user
    useEffect(() => {
        const hasSeenWelcome = localStorage.getItem('remis_has_seen_welcome');
        if (!hasSeenWelcome) {
            // We can trigger a gentle prompt here or wait for the home page to mount
            // For now, we'll just set the flag when they actually start a tour or manually.
        }
    }, []);

    return (
        <TutorialContext.Provider value={{ startTour, isTourActive, pageContext, setPageContext }}>
            {children}
        </TutorialContext.Provider>
    );
};
