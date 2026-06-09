import { createContext, useContext } from 'react';

export const TutorialContext = createContext();

export const TUTORIAL_VERSION = 'v1';
export const getTutorialKey = (page = 'general') => `remis_tutorial_${page}_${TUTORIAL_VERSION}`;

export const useTutorial = () => {
    const context = useContext(TutorialContext);
    if (!context) {
        throw new Error('useTutorial must be used within a TutorialProvider');
    }
    return context;
};
