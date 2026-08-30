import React from 'react';

import ModArchiveAnalysisSetup from './ModArchiveAnalysisSetup';
import { useModArchiveAnalysis } from './useModArchiveAnalysis';

/**
 * Compatibility entry point for the existing neologism route.
 * Workflow/API state lives in the archive controller; this component only
 * connects the controller to the maintained analysis presentation.
 */
const MiningDashboard = (props) => {
    const controller = useModArchiveAnalysis(props);
    return <ModArchiveAnalysisSetup controller={controller} />;
};

export default MiningDashboard;
