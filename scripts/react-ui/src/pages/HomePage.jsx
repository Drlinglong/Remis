import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { useTutorial } from '../context/TutorialContextCore';
import HomeDashboardView from './home/HomeDashboardView';
import { getHomeGreeting } from './home/homeDashboardModel';
import { useHomeDashboardData } from './home/useHomeDashboardData';
import { useHomeLiveWork } from './home/useHomeLiveWork';

const HomePage = () => {
  const { t, i18n } = useTranslation();
  const { setPageContext } = useTutorial();
  const dashboard = useHomeDashboardData({ language: i18n.language });
  const liveWork = useHomeLiveWork();

  useEffect(() => {
    setPageContext((previous) => (previous === 'home' ? previous : 'home'));
  }, [setPageContext]);

  return (
    <HomeDashboardView
      dashboard={dashboard}
      greeting={getHomeGreeting(t)}
      liveWork={liveWork}
      t={t}
    />
  );
};

export default HomePage;
