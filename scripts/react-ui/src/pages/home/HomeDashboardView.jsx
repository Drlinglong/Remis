import React from 'react';
import { Alert, Box, Button, Card, Grid, Group, Skeleton, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle, IconBriefcase, IconChecklist, IconPlayerPlay } from '@tabler/icons-react';

import ProjectDistributionPieChart from '../../components/ProjectDistributionPieChart';
import ProjectStatusPieChart from '../../components/ProjectStatusPieChart';
import RecentActivityList from '../../components/RecentActivityList';
import StatCard from '../../components/StatCard';
import styles from '../HomePage.module.css';
import HomeLiveWorkSection from './HomeLiveWorkSection';

const metricValue = (value) => (value == null ? '—' : String(value));
const progressValue = (value) => (value == null ? 0 : Math.max(0, Math.min(100, value)));

function ChartPlaceholder() {
  return (
    <Stack className={styles.chartFrame} gap="sm" aria-label="home-chart-loading">
      <Skeleton height={220} circle />
      <Skeleton height={12} width="64%" mx="auto" />
    </Stack>
  );
}

export default function HomeDashboardView({ dashboard, greeting, liveWork, t }) {
  const { charts, recentActivity, stats } = dashboard.data;
  const dashboardError = dashboard.error?.response?.data?.detail
    || dashboard.error?.message
    || t('homepage_dashboard_error', { defaultValue: 'Dashboard data is temporarily unavailable.' });

  return (
    <Box className={styles.pageScroll} data-remis-surface="canvas">
      <Box className={styles.content} p={{ base: 'md', lg: 'xl' }} maw={1500} mx="auto">
        <Group id="homepage-workspace-header" align="flex-start" mb="lg" gap="md">
          <div className={styles.headerCopy}>
            <Text size="sm" fw={700} c="dimmed" tt="uppercase">
              {t('homepage_workspace_eyebrow')}
            </Text>
            <Title order={1} className={styles.pageTitle}>{greeting}</Title>
            <Text c="dimmed" className={styles.bodyMeasure}>{t('homepage_workspace_subtitle')}</Text>
          </div>
        </Group>

        {dashboard.phase === 'error' && (
          <Alert
            mb="md"
            color="red"
            icon={<IconAlertTriangle size={19} />}
            data-remis-surface="paper"
            data-remis-region="dashboard-error"
            className={styles.dashboardError}
          >
            <Group justify="space-between" align="flex-start" gap="md" wrap="wrap">
              <Text className={styles.longText}>{dashboardError}</Text>
              <Button
                variant="default"
                size="compact-sm"
                data-remis-action="paper-secondary"
                style={{ '--button-color': 'var(--paper-text-main)', '--button-hover-color': 'var(--paper-text-main)' }}
                styles={{ label: { color: 'var(--paper-text-main)', WebkitTextFillColor: 'currentColor' } }}
                onClick={dashboard.refresh}
              >
                {t('task_center.retry', { defaultValue: 'Retry' })}
              </Button>
            </Group>
          </Alert>
        )}

        <Grid gutter="md" mb="md" align="stretch">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <HomeLiveWorkSection t={t} workflow={liveWork} />
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap="md" className={styles.statsRail}>
              <StatCard
                title={t('homepage_stat_total_projects')}
                value={metricValue(stats.total_projects)}
                icon={<IconBriefcase size={22} />}
                color="blue"
                progress={stats.total_projects == null ? 0 : 100}
                className={styles.statCard}
              />
              <StatCard
                title={t('homepage_stat_active_projects')}
                value={metricValue(stats.active_projects)}
                icon={<IconPlayerPlay size={22} />}
                color="teal"
                progress={stats.active_projects == null ? 0 : progressValue(
                  (stats.active_projects / (stats.total_projects || 1)) * 100,
                )}
                className={styles.statCard}
              />
              <StatCard
                title={t('homepage_stat_completion_rate')}
                value={stats.completion_rate == null ? '—' : `${stats.completion_rate}%`}
                icon={<IconChecklist size={22} />}
                color="grape"
                progress={progressValue(stats.completion_rate)}
                className={styles.statCard}
              />
            </Stack>
          </Grid.Col>
        </Grid>

        <Grid gutter="md" align="start">
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Card
              id="homepage-project-portfolio"
              withBorder
              radius="md"
              p={{ base: 'md', sm: 'lg' }}
              className={styles.portfolio}
              data-remis-surface="surface"
            >
              <Title order={3} mb="md">{t('homepage_project_portfolio')}</Title>
              <Grid gutter="md">
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  {dashboard.phase === 'loading' ? <ChartPlaceholder /> : (
                    <ProjectStatusPieChart data={charts.project_status} />
                  )}
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  {dashboard.phase === 'loading' ? <ChartPlaceholder /> : (
                    <ProjectDistributionPieChart data={charts.project_distribution} />
                  )}
                </Grid.Col>
              </Grid>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <RecentActivityList
              id="recent-activity"
              className={styles.activity}
              activities={recentActivity}
              loading={dashboard.phase === 'loading'}
              error={dashboard.phase === 'error'}
              emptyLabel={t('homepage_recent_activity_unavailable', {
                defaultValue: 'Recent activity is unavailable until the dashboard reconnects.',
              })}
            />
          </Grid.Col>
        </Grid>
      </Box>
    </Box>
  );
}
