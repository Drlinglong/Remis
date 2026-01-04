import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Grid, Card, Title, Text, ThemeIcon, Group, Stack, Box, Button, BackgroundImage, Overlay, ActionIcon, ScrollArea, Modal } from '@mantine/core';
import { IconRocket, IconRefresh, IconChartBar, IconVocabulary, IconChecklist, IconActivity, IconTools } from '@tabler/icons-react';
import ActionCard from '../components/ActionCard';
import ProjectStatusPieChart from '../components/ProjectStatusPieChart';
import ProjectDistributionPieChart from '../components/ProjectDistributionPieChart';
import GlossaryAnalysisBarChart from '../components/GlossaryAnalysisBarChart';
import StatCard from '../components/StatCard';
import RecentActivityList from '../components/RecentActivityList';

import api from '../utils/api';
import styles from './HomePage.module.css';
import { useTutorial, getTutorialKey } from '../context/TutorialContext';

const HomePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { startTour, setPageContext } = useTutorial();
  const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);

  useEffect(() => {
    setPageContext('home');
  }, [setPageContext]);
  const [slogan, setSlogan] = useState('');
  const [greeting, setGreeting] = useState('');
  const [stats, setStats] = useState({
    total_projects: 0,
    words_translated: 0,
    active_tasks: 0,
    completion_rate: 0
  });
  const [charts, setCharts] = useState({
    project_status: [],
    glossary_analysis: [],
    project_distribution: []
  });
  const [recentActivity, setRecentActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const slogans = t('homepage_slogans', { returnObjects: true });
    if (Array.isArray(slogans) && slogans.length > 0) {
      const randomIndex = Math.floor(Math.random() * slogans.length);
      setSlogan(slogans[randomIndex]);
    }

    const hour = new Date().getHours();
    let timeKey = 'morning';
    if (hour >= 12 && hour < 18) timeKey = 'afternoon';
    else if (hour >= 18 || hour < 5) timeKey = 'evening';

    const timeGreetings = t('homepage_greetings', { returnObjects: true })?.[timeKey];
    if (Array.isArray(timeGreetings) && timeGreetings.length > 0) {
      const randomGreetingIndex = Math.floor(Math.random() * timeGreetings.length);
      setGreeting(timeGreetings[randomGreetingIndex]);
    } else {
      // Fallback
      if (hour < 12) setGreeting('Good Morning');
      else if (hour < 18) setGreeting('Good Afternoon');
      else setGreeting('Good Evening');
    }

    fetchDashboardData();

    // Check for first-time user
    const tutorialKey = getTutorialKey('prompt_seen');
    const hasSeenTutorialPrompt = localStorage.getItem(tutorialKey);
    if (!hasSeenTutorialPrompt) {
      setShowTutorialPrompt(true);
    }
  }, [t]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/system/stats');
      const data = response.data;
      setStats(data.stats);
      setCharts(data.charts);
      setRecentActivity(data.recent_activity);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box h="100vh" style={{ overflow: 'hidden' }}>
      <Modal
        opened={showTutorialPrompt}
        onClose={() => {
          setShowTutorialPrompt(false);
          localStorage.setItem(getTutorialKey('prompt_seen'), 'true');
        }}
        title={t('tutorial.auto_start_prompt.title')}
        centered
        className={styles.glassModal}
      >
        <Stack>
          <Text>{t('tutorial.auto_start_prompt.message')}</Text>
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" color="gray" onClick={() => {
              setShowTutorialPrompt(false);
              localStorage.setItem(getTutorialKey('prompt_seen'), 'true');
            }}>
              {t('tutorial.auto_start_prompt.cancel')}
            </Button>
            <Button color="blue" onClick={() => {
              setShowTutorialPrompt(false);
              localStorage.setItem(getTutorialKey('prompt_seen'), 'true');
              startTour('home');
            }}>
              {t('tutorial.auto_start_prompt.confirm')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <ScrollArea h="100%" type="scroll">
        <Box p="md">
          {/* Welcome Banner */}
          <Box
            id="welcome-banner"
            mb="xl"
            className={styles.welcomeBanner}
            p={40}
          >
            <Stack style={{ position: 'relative', zIndex: 2 }}>
              <Title order={1} className={styles.cardTitle} style={{ fontSize: '2.4rem', fontWeight: 800 }}>
                {greeting}
              </Title>
              <Text size="lg" style={{ opacity: 0.9, maxWidth: '600px', color: 'var(--text-main)' }}>
                "{slogan}"
              </Text>
              <Group mt="lg">
                <Button
                  size="md"
                  radius="md"
                  leftSection={<IconRocket size={20} />}
                  className={styles.actionButton}
                  onClick={() => navigate('/project-management')}
                >
                  {t('homepage_action_card_new_project')}
                </Button>
                {/* <Button size="md" radius="md" leftSection={<IconRefresh size={20} />} className={styles.actionButton}>
                  {t('homepage_action_card_update_project')}
                </Button> */}
              </Group>
            </Stack>

            {/* Decorative Background Elements */}
            <IconRocket
              size={300}
              className={styles.floatingIcon}
              style={{
                position: 'absolute',
                right: -50,
                bottom: -50,
                opacity: 0.08,
                color: 'var(--text-highlight)',
                pointerEvents: 'none'
              }}
            />
          </Box>

          {/* Key Metrics Row */}
          <Grid id="stat-cards" gutter="md" mb="xl">
            <Grid.Col span={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard
                title={t('homepage_stat_total_projects')}
                value={stats.total_projects.toString()}
                icon={<IconChecklist size={24} />}
                color="blue"
                progress={100}
                trend={0}
                className={styles.glassCard}
              />
            </Grid.Col>
            <Grid.Col span={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard
                title={t('homepage_stat_words_translated')}
                value={stats.words_translated.toLocaleString()}
                icon={<IconVocabulary size={24} />}
                color="teal"
                progress={stats.completion_rate}
                trend={0}
                className={styles.glassCard}
              />
            </Grid.Col>
            <Grid.Col span={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard
                title={t('homepage_stat_active_tasks')}
                value={stats.active_tasks.toString()}
                icon={<IconActivity size={24} />}
                color="orange"
                progress={Math.min(100, (stats.active_tasks / (stats.total_projects || 1)) * 100)}
                trend={0}
                className={styles.glassCard}
              />
            </Grid.Col>
            <Grid.Col span={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard
                title={t('homepage_stat_completion_rate')}
                value={`${stats.completion_rate}%`}
                icon={<IconChartBar size={24} />}
                color="grape"
                progress={stats.completion_rate}
                trend={0}
                className={styles.glassCard}
              />
            </Grid.Col>
          </Grid>

          {/* Main Dashboard Content */}
          <Grid gutter="md">
            {/* Left Column: Charts */}
            <Grid.Col span={{ xs: 12, lg: 8 }}>
              <Stack gap="md">
                <Card shadow="sm" padding="lg" radius="md" withBorder className={styles.glassCard}>
                  <Group justify="space-between" mb="md">
                    <Title order={4} className={styles.cardTitle}>{t('homepage_chart_pie_title')}</Title>
                    <ActionIcon variant="subtle" color="gray" onClick={fetchDashboardData} loading={loading}><IconRefresh size={16} /></ActionIcon>
                  </Group>
                  <Grid>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Text ta="center" size="sm" c="dimmed" mb="xs">{t('homepage_pie_chart_status_title', 'By Status')}</Text>
                      <ProjectStatusPieChart data={charts.project_status} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Text ta="center" size="sm" c="dimmed" mb="xs">{t('homepage_pie_chart_distribution_title', 'By Game')}</Text>
                      <ProjectDistributionPieChart data={charts.project_distribution} />
                    </Grid.Col>
                  </Grid>
                </Card>
                <Card shadow="sm" padding="lg" radius="md" withBorder className={styles.glassCard}>
                  <Group justify="space-between" mb="md">
                    <Title order={4} className={styles.cardTitle}>{t('homepage_chart_bar_title')}</Title>
                    <ActionIcon variant="subtle" color="gray" onClick={fetchDashboardData} loading={loading}><IconRefresh size={16} /></ActionIcon>
                  </Group>
                  <GlossaryAnalysisBarChart data={charts.glossary_analysis} />
                </Card>
              </Stack>
            </Grid.Col>

            {/* Right Column: Recent Activity & Quick Actions */}
            <Grid.Col span={{ xs: 12, lg: 4 }}>
              <Stack gap="md">
                <RecentActivityList
                  id="recent-activity"
                  className={styles.glassCard}
                  activities={recentActivity}
                  loading={loading}
                />

                <Card id="quick-links" shadow="sm" padding="lg" radius="md" withBorder className={styles.glassCard}>
                  <Title order={4} mb="md" className={styles.cardTitle}>{t('homepage_quick_links')}</Title>
                  <Stack gap="xs">
                    <Button
                      variant="light"
                      color="blue"
                      fullWidth
                      justify="flex-start"
                      leftSection={<IconTools size={16} />}
                      className={styles.actionButton}
                      onClick={() => navigate('/tools')}
                    >
                      {t('homepage_quick_link_toolbox')}
                    </Button>
                    <Button
                      variant="light"
                      color="teal"
                      fullWidth
                      justify="flex-start"
                      leftSection={<IconRefresh size={16} />}
                      className={styles.actionButton}
                      onClick={() => navigate('/glossary-manager')}
                    >
                      {t('homepage_quick_link_glossary')}
                    </Button>
                    <Button
                      variant="light"
                      color="orange"
                      fullWidth
                      justify="flex-start"
                      leftSection={<IconChecklist size={16} />}
                      className={styles.actionButton}
                      onClick={() => navigate('/proofreading')}
                    >
                      {t('homepage_quick_link_proofreading')}
                    </Button>
                  </Stack>
                </Card>
              </Stack>
            </Grid.Col>
          </Grid>
        </Box>
      </ScrollArea>
    </Box>
  );
};

export default HomePage;
