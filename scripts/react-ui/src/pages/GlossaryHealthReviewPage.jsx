import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconArrowLeft } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import GlossaryHealthWorkbench from '../components/glossary/GlossaryHealthWorkbench';
import GlossaryHealthPenaltyBreakdown from '../components/glossary/GlossaryHealthPenaltyBreakdown';
import api from '../utils/api';
import { taskDetailRoute } from '../utils/taskRoutes';
import { useTutorial } from '../context/TutorialContextCore';
import styles from './GlossaryHealthReviewPage.module.css';

const GlossaryHealthReviewPage = () => {
  const { taskId = '' } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setPageContext } = useTutorial();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadTask = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/tasks/${encodeURIComponent(taskId)}`);
      setTask(response.data);
      setError('');
    } catch (loadError) {
      setError(loadError.response?.data?.detail || loadError.message || t('task_detail.load_error'));
    } finally {
      setLoading(false);
    }
  }, [t, taskId]);

  useEffect(() => {
    loadTask();
  }, [loadTask]);

  useEffect(() => {
    setPageContext('glossary-health-review');
  }, [setPageContext]);

  const isGlossaryHealthTask = useMemo(() => (
    (task?.result?.types || []).includes('glossary_health_report')
  ), [task]);
  const report = task?.result?.metadata || {};

  if (loading) {
    return <Group justify="center" h="100%"><Loader /></Group>;
  }

  if (error || !task || !isGlossaryHealthTask) {
    return (
      <Box className={styles.page}>
        <Alert
          color="red"
          title={t('task_detail.load_error')}
          icon={<IconAlertTriangle size={18} />}
          className={styles.error}
        >
          <Stack gap="sm">
            <Text>{error || t('task_detail.not_available')}</Text>
            <Group>
              <Button variant="default" onClick={() => navigate(taskDetailRoute(taskId))}>
                {t('button_back')}
              </Button>
              {error && <Button variant="light" onClick={loadTask}>{t('button_refresh')}</Button>}
            </Group>
          </Stack>
        </Alert>
      </Box>
    );
  }

  return (
    <Box className={styles.page}>
      <Box id="glossary-health-review-header" component="header" className={styles.header}>
        <Button
          variant="subtle"
          color="gray"
          leftSection={<IconArrowLeft size={17} />}
          onClick={() => navigate(taskDetailRoute(task.task_id))}
          className={styles.backButton}
        >
          {t('button_back')}
        </Button>
        <Stack gap={4} className={styles.heading}>
          <Title order={1}>{t('glossary_health_workbench', { defaultValue: 'Review and fix issues' })}</Title>
          <Text size="sm" c="dimmed">
            {t('glossary_health_workbench_desc', { defaultValue: 'Select an issue, inspect its evidence, and edit the live glossary entry.' })}
          </Text>
        </Stack>
        <Group gap="xs" className={styles.summary}>
          <Badge color={report.score >= 80 ? 'teal' : report.score >= 60 ? 'orange' : 'red'}>
            {t('glossary_health_score', 'Score')} {report.score}/100
          </Badge>
          <Badge variant="light">
            {report.issue_count || 0} {t('glossary_health_issues', 'issues')}
          </Badge>
          <GlossaryHealthPenaltyBreakdown issues={report.issues} />
        </Group>
      </Box>

      <Box id="glossary-health-review-workbench" className={styles.workbench}>
        <GlossaryHealthWorkbench report={report} />
      </Box>
    </Box>
  );
};

export default GlossaryHealthReviewPage;
