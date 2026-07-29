import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Card, Grid, Group, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle, IconBriefcase, IconChecklist, IconHistory, IconPlayerPlay, IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import ProjectDistributionPieChart from '../components/ProjectDistributionPieChart';
import ProjectStatusPieChart from '../components/ProjectStatusPieChart';
import RecentActivityList from '../components/RecentActivityList';
import StatCard from '../components/StatCard';
import { TaskSummaryCard } from '../components/tasks/TaskSummaryCard';
import { useTaskCenter } from '../context/TaskCenterContextCore';
import { useTutorial } from '../context/TutorialContextCore';
import api from '../utils/api';
import { taskDetailRoute } from '../utils/taskRoutes';
import styles from './HomePage.module.css';

const HomePage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { setPageContext } = useTutorial();
  const {
    attentionCount,
    loading: tasksLoading,
    refreshTasks,
    tasks,
  } = useTaskCenter();
  const [greeting, setGreeting] = useState('');
  const [stats, setStats] = useState({
    total_projects: 0,
    words_translated: 0,
    active_projects: 0,
    completion_rate: 0,
  });
  const [charts, setCharts] = useState({ project_status: [], project_distribution: [] });
  const [recentActivity, setRecentActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [handlingTaskId, setHandlingTaskId] = useState('');
  const [handleError, setHandleError] = useState('');

  useEffect(() => {
    setPageContext((prev) => (prev === 'home' ? prev : 'home'));
  }, [setPageContext]);

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get('/api/system/stats');
      setStats({
        ...data.stats,
        active_projects: data.stats?.active_projects ?? data.stats?.active_tasks ?? 0,
      });
      setCharts(data.charts || {});
      setRecentActivity(data.recent_activity || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const hour = new Date().getHours();
    const timeKey = hour >= 18 || hour < 5 ? 'evening' : hour >= 12 ? 'afternoon' : 'morning';
    const options = t('homepage_greetings', { returnObjects: true })?.[timeKey];
    setGreeting(Array.isArray(options) && options.length > 0 ? options[0] : t('homepage_workspace_title'));
    fetchDashboardData();
  }, [fetchDashboardData, i18n.language, t]);

  const visibleTasks = useMemo(() => {
    const actionableTasks = tasks.filter((task) => (
      ['queued', 'running', 'awaiting_approval', 'failed', 'interrupted'].includes(task.status)
    ));
    const latestCompletedTask = tasks.find((task) => task.status === 'completed');
    if (!latestCompletedTask) return actionableTasks.slice(0, 3);
    return [...actionableTasks.slice(0, 2), latestCompletedTask];
  }, [tasks]);

  const openTask = (task) => navigate(taskDetailRoute(task.task_id));
  const markHandled = async (task) => {
    setHandlingTaskId(task.task_id);
    setHandleError('');
    try {
      await api.post(`/api/tasks/${encodeURIComponent(task.task_id)}/archive`);
      await refreshTasks({ quiet: true });
    } catch (error) {
      setHandleError(error.response?.data?.detail || error.message || t('task_center.handle_error'));
    } finally {
      setHandlingTaskId('');
    }
  };

  return (
    <Box h="100vh" className={styles.pageScroll} data-remis-surface="canvas">
      <Box p={{ base: 'md', lg: 'xl' }} maw={1500} mx="auto">
        <Group id="homepage-workspace-header" align="flex-start" mb="lg" gap="md">
          <div>
            <Text size="sm" fw={700} c="dimmed" tt="uppercase">{t('homepage_workspace_eyebrow')}</Text>
            <Title order={1} className={styles.pageTitle}>{greeting}</Title>
            <Text c="dimmed" maw={680}>{t('homepage_workspace_subtitle')}</Text>
          </div>
        </Group>

        {attentionCount > 0 && (
          <Alert
            mb="md"
            color="orange"
            icon={<IconAlertTriangle size={19} />}
            data-remis-surface="paper"
            style={{
              background: 'var(--paper-bg)',
              border: '1px solid var(--interactive-accent)',
            }}
            styles={{
              icon: { color: 'var(--paper-text-main)' },
              message: { color: 'var(--paper-text-main)' },
            }}
          >
            {t('task_center.attention_summary', { count: attentionCount })}
          </Alert>
        )}

        <Grid gutter="md" mb="md">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Card
              id="homepage-live-work"
              withBorder
              radius="md"
              p="lg"
              className={styles.glassCard}
              h="100%"
              data-remis-surface="surface"
            >
              <Group justify="space-between" mb="md">
                <div>
                  <Title order={3}>{t('homepage_live_work_title')}</Title>
                  <Text size="sm" c="dimmed">{t('homepage_live_work_subtitle')}</Text>
                </div>
                <Group gap={4} wrap="nowrap">
                  <Button
                    variant="subtle"
                    size="compact-sm"
                    leftSection={<IconHistory size={15} />}
                    onClick={() => navigate('/task-history')}
                  >
                    {t('task_center.view_history')}
                  </Button>
                  <Button
                    variant="subtle"
                    size="compact-sm"
                    leftSection={<IconRefresh size={15} />}
                    loading={tasksLoading}
                    onClick={() => refreshTasks()}
                  >
                    {t('button_refresh')}
                  </Button>
                </Group>
              </Group>
              {handleError && <Alert color="red" mb="sm">{handleError}</Alert>}
              {visibleTasks.length > 0 ? (
                <Stack gap="sm">
                  {visibleTasks.map((task) => (
                    <TaskSummaryCard
                      compact
                      key={task.task_id}
                      task={task}
                      handling={handlingTaskId === task.task_id}
                      onHandle={markHandled}
                      onOpen={openTask}
                    />
                  ))}
                </Stack>
              ) : (
                <Stack align="center" justify="center" mih={180} gap="xs">
                  <Text fw={700}>{tasksLoading ? t('loading') : t('task_center.empty_title')}</Text>
                  <Text size="sm" c="dimmed" ta="center">{t('homepage_live_work_empty')}</Text>
                  <Button variant="light" onClick={() => navigate('/project-management')}>
                    {t('homepage_action_continue_project')}
                  </Button>
                </Stack>
              )}
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap="md" h="100%">
              <StatCard
                title={t('homepage_stat_total_projects')}
                value={stats.total_projects.toString()}
                icon={<IconBriefcase size={22} />}
                color="blue"
                progress={100}
                trend={0}
                className={styles.glassCard}
              />
              <StatCard
                title={t('homepage_stat_active_projects')}
                value={stats.active_projects.toString()}
                icon={<IconPlayerPlay size={22} />}
                color="teal"
                progress={Math.min(100, (stats.active_projects / (stats.total_projects || 1)) * 100)}
                trend={0}
                className={styles.glassCard}
              />
              <StatCard
                title={t('homepage_stat_completion_rate')}
                value={`${stats.completion_rate}%`}
                icon={<IconChecklist size={22} />}
                color="grape"
                progress={stats.completion_rate}
                trend={0}
                className={styles.glassCard}
              />
            </Stack>
          </Grid.Col>
        </Grid>

        <Grid gutter="md">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Card id="homepage-project-portfolio" withBorder radius="md" p="lg" className={styles.glassCard}>
              <Title order={3} mb="md">{t('homepage_project_portfolio')}</Title>
              <Grid>
                <Grid.Col span={{ base: 12, sm: 6 }}><ProjectStatusPieChart data={charts.project_status || []} /></Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}><ProjectDistributionPieChart data={charts.project_distribution || []} /></Grid.Col>
              </Grid>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <RecentActivityList
              id="recent-activity"
              className={styles.glassCard}
              activities={recentActivity}
              loading={loading}
            />
          </Grid.Col>
        </Grid>
      </Box>
    </Box>
  );
};

export default HomePage;
