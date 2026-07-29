import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Code,
  Group,
  Loader,
  Modal,
  Paper,
  SegmentedControl,
  Stack,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconChartBar,
  IconHistory,
  IconPlayerPlay,
  IconShieldCheck,
  IconSparkles,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import ArenaHistory from '../components/modelArena/ArenaHistory';
import ArenaResults from '../components/modelArena/ArenaResults';
import ArenaRunStatus from '../components/modelArena/ArenaRunStatus';
import ArenaSetup from '../components/modelArena/ArenaSetup';
import ArenaVoting from '../components/modelArena/ArenaVoting';
import modelArenaService from '../services/modelArenaService';
import styles from './ModelArenaPage.module.css';

const arenaModalClassNames = {
  content: styles.modalContent,
  header: styles.modalHeader,
  title: styles.modalTitle,
  body: styles.modalBody,
  close: styles.modalClose,
};

const initialValues = {
  project_id: '',
  target_lang_code: '',
  sample_size: 6,
  use_project_context: true,
  contestants: [
    { provider_id: '', model_id: '' },
    { provider_id: '', model_id: '' },
  ],
};

const runStage = (run) => {
  if (!run || run.status === 'draft') return 0;
  if (['queued', 'running', 'failed'].includes(run.status)) return 1;
  if (['voting', 'partial_failed'].includes(run.status)) return 2;
  return 3;
};

const errorMessage = (error, fallback) => (
  error?.response?.data?.detail || error?.message || fallback
);

export default function ModelArenaPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedRunId = searchParams.get('run');
  const [activeTab, setActiveTab] = useState('arena');
  const [bootstrap, setBootstrap] = useState({ projects: [], providers: [], languages: {} });
  const [values, setValues] = useState(initialValues);
  const [run, setRun] = useState(null);
  const [votes, setVotes] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [savingVote, setSavingVote] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState('');
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [approvalAction, setApprovalAction] = useState('start');
  const [approved, setApproved] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [previewTarget, setPreviewTarget] = useState(null);
  const [previewMode, setPreviewMode] = useState('evidence');
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const suppressedRunIdRef = useRef(null);

  const stage = runStage(run);

  const restoreDraftValues = useCallback((detail) => {
    if (detail?.status !== 'draft') return;
    setValues({
      project_id: String(detail.project_id || ''),
      target_lang_code: detail.target_lang_code || '',
      sample_size: Number(detail.sample_size || 6),
      use_project_context: Boolean(
        detail.settings?.use_project_glossaries || detail.settings?.use_mod_context,
      ),
      contestants: (detail.contestants || []).map((contestant) => ({
        provider_id: contestant.provider_id,
        model_id: contestant.model_id,
      })),
    });
  }, []);

  const clearActiveRun = useCallback(() => {
    suppressedRunIdRef.current = run?.run_id || requestedRunId || null;
    setSearchParams({}, { replace: true });
    setRun(null);
    setVotes({});
    setActiveTab('arena');
    setApprovalOpen(false);
    setApproved(false);
  }, [requestedRunId, run?.run_id, setSearchParams]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const result = await modelArenaService.listRuns({ limit: 100, offset: 0 });
      setHistory(result.runs);
      setError('');
    } catch (loadError) {
      setError(errorMessage(loadError, t('model_arena.error_generic')));
    } finally {
      setHistoryLoading(false);
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    modelArenaService.loadBootstrap()
      .then((data) => {
        if (cancelled) return;
        setBootstrap(data);
        setValues((current) => {
          const firstProvider = data.providers.find((provider) => provider.configured !== false)
            || data.providers[0];
          const providerId = firstProvider?.value || firstProvider?.id || '';
          const modelId = firstProvider?.selected_model
            || firstProvider?.available_models?.[0]
            || firstProvider?.custom_models?.[0]
            || '';
          return {
            ...current,
            project_id: current.project_id
              || String(data.projects[0]?.project_id || data.projects[0]?.value || ''),
            contestants: current.contestants.map((contestant) => (
              contestant.provider_id ? contestant : { provider_id: providerId, model_id: modelId }
            )),
          };
        });
      })
      .catch((loadError) => {
        if (!cancelled) setError(errorMessage(loadError, t('model_arena.error_generic')));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [t]);

  useEffect(() => {
    if (
      !requestedRunId
      || run?.run_id === requestedRunId
      || suppressedRunIdRef.current === requestedRunId
    ) return;
    let cancelled = false;
    setLoading(true);
    modelArenaService.getRun(requestedRunId)
      .then((detail) => {
        if (cancelled) return;
        setRun(detail);
        restoreDraftValues(detail);
        setVotes(Object.fromEntries(
          (detail.samples || [])
            .filter((sample) => sample.vote)
            .map((sample) => [sample.sample_id, sample.vote]),
        ));
      })
      .catch((loadError) => {
        if (!cancelled) setError(errorMessage(loadError, t('model_arena.error_generic')));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [requestedRunId, restoreDraftValues, run?.run_id, t]);

  useEffect(() => {
    if (activeTab === 'history') loadHistory();
  }, [activeTab, loadHistory]);

  const refreshRun = useCallback(async () => {
    if (!run?.run_id) return;
    try {
      const nextRun = await modelArenaService.getRun(run.run_id);
      if (suppressedRunIdRef.current === nextRun.run_id) return;
      setRun(nextRun);
      setVotes(Object.fromEntries(
        (nextRun.samples || [])
          .filter((sample) => sample.vote)
          .map((sample) => [sample.sample_id, sample.vote]),
      ));
      setError('');
    } catch (refreshError) {
      setError(errorMessage(refreshError, t('model_arena.error_generic')));
    }
  }, [run?.run_id, t]);

  useEffect(() => {
    if (!run?.run_id || !['queued', 'running'].includes(run.status)) return undefined;
    const intervalId = window.setInterval(refreshRun, 1500);
    return () => window.clearInterval(intervalId);
  }, [refreshRun, run?.run_id, run?.status]);

  const createDraft = async () => {
    setLoading(true);
    try {
      const nextRun = await modelArenaService.createRun({
        project_id: values.project_id,
        target_lang_code: values.target_lang_code,
        sample_size: values.sample_size,
        use_project_glossaries: values.use_project_context,
        use_mod_context: values.use_project_context,
        contestants: values.contestants,
        sampler_version: 'representative_v1',
      });
      suppressedRunIdRef.current = null;
      setRun(nextRun);
      setSearchParams({ run: nextRun.run_id });
      setVotes({});
      setError('');
    } catch (createError) {
      setError(errorMessage(createError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const resample = async () => {
    setLoading(true);
    try {
      setRun(await modelArenaService.resample(run.run_id));
      setError('');
    } catch (resampleError) {
      setError(errorMessage(resampleError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const editDraft = async () => {
    if (!run?.run_id || run.status !== 'draft') return;
    setLoading(true);
    try {
      await modelArenaService.deleteRun(run.run_id);
      clearActiveRun();
      setError('');
    } catch (editError) {
      setError(errorMessage(editError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const startRun = async () => {
    setLoading(true);
    try {
      setRun(await modelArenaService.startRun(run.run_id));
      setApprovalOpen(false);
      setApproved(false);
      setError('');
    } catch (startError) {
      setError(errorMessage(startError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const saveVote = async (sampleId, payload) => {
    setSavingVote(true);
    try {
      const saved = await modelArenaService.saveVote(run.run_id, sampleId, payload);
      setVotes((current) => ({ ...current, [sampleId]: saved || payload }));
      setError('');
    } catch (voteError) {
      setError(errorMessage(voteError, t('model_arena.error_generic')));
      throw voteError;
    } finally {
      setSavingVote(false);
    }
  };

  const completeRun = async () => {
    setLoading(true);
    try {
      setRun(await modelArenaService.completeRun(run.run_id));
      setError('');
    } catch (completeError) {
      setError(errorMessage(completeError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const retryFailures = async () => {
    setRetrying(true);
    try {
      setRun(await modelArenaService.retryFailures(run.run_id));
      setApprovalOpen(false);
      setApproved(false);
      setError('');
    } catch (retryError) {
      setError(errorMessage(retryError, t('model_arena.error_generic')));
    } finally {
      setRetrying(false);
    }
  };

  const openHistoricalRun = async (summary) => {
    setLoading(true);
    try {
      const detail = await modelArenaService.getRun(summary.run_id);
      suppressedRunIdRef.current = null;
      setRun(detail);
      restoreDraftValues(detail);
      setSearchParams({ run: detail.run_id });
      setActiveTab('arena');
      setVotes(Object.fromEntries(
        (detail.samples || [])
          .filter((sample) => sample.vote)
          .map((sample) => [sample.sample_id, sample.vote]),
      ));
    } catch (openError) {
      setError(errorMessage(openError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const loadPreview = useCallback(async (target, mode = previewMode) => {
    if (!target?.run_id) return;
    setPreviewTarget(target);
    setPreviewMode(mode);
    setPreviewLoading(true);
    try {
      setPreview(await modelArenaService.getExportPreview(target.run_id, mode));
    } catch (previewError) {
      setError(errorMessage(previewError, t('model_arena.error_generic')));
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [previewMode, t]);

  const exportRun = async () => {
    setPreviewLoading(true);
    try {
      const response = await modelArenaService.exportRun(previewTarget.run_id, previewMode);
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `remis-model-arena-${previewTarget.run_id}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      const encodedExportPath = response.headers?.['x-remis-export-path'];
      if (encodedExportPath) {
        await modelArenaService.openExportPath(decodeURIComponent(encodedExportPath));
      }
    } catch (exportError) {
      setError(errorMessage(exportError, t('model_arena.error_generic')));
    } finally {
      setPreviewLoading(false);
    }
  };

  const deleteRun = async () => {
    setLoading(true);
    try {
      await modelArenaService.deleteRun(deleteTarget.run_id);
      if (run?.run_id === deleteTarget.run_id) {
        clearActiveRun();
      }
      setDeleteTarget(null);
      await loadHistory();
    } catch (deleteError) {
      setError(errorMessage(deleteError, t('model_arena.error_generic')));
    } finally {
      setLoading(false);
    }
  };

  const stageLabels = useMemo(() => [
    t('model_arena.step_setup'),
    t('model_arena.step_run'),
    t('model_arena.step_vote'),
    t('model_arena.step_results'),
  ], [t]);
  const retryContestantCount = (run?.contestants || []).filter(
    (contestant) => contestant.status === 'failed',
  ).length;
  const approvalModelCount = approvalAction === 'retry'
    ? retryContestantCount
    : (run?.contestants?.length || values.contestants.length);
  const approvalRequestCount = approvalAction === 'retry'
    ? retryContestantCount
    : (run?.estimated_request_count || approvalModelCount);

  return (
    <Box className={styles.page} data-remis-surface="canvas">
      <Stack className={styles.shell} gap="lg">
        <Box className={styles.hero} data-remis-surface="canvas">
          <Group className={styles.heroHeader} justify="space-between" align="flex-start">
            <div className={styles.heroCopy}>
              <Group gap="xs">
                <IconSparkles className={styles.heroIcon} size={28} />
                <Title className={styles.heroTitle} order={1}>
                  {t('page_title_model_arena')}
                </Title>
              </Group>
              <Text className={styles.heroSubtitle} maw={780} mt="xs">
                {t('model_arena.subtitle')}
              </Text>
            </div>
            {run && (
              <Button
                variant="default"
                onClick={clearActiveRun}
              >
                {t('model_arena.new_arena')}
              </Button>
            )}
          </Group>
          {activeTab === 'arena' && (
            <Box component="ol" className={styles.stageSteps} mt="md">
              {stageLabels.map((label, index) => (
                <Box
                  component="li"
                  key={label}
                    className={styles.stageStep}
                    data-current={stage === index || undefined}
                    data-complete={stage > index || undefined}
                >
                  <span className={styles.stageIndex}>{index + 1}</span>
                  <span>{label}</span>
                </Box>
              ))}
            </Box>
          )}
        </Box>

        {error && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} withCloseButton onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        <Tabs className={styles.tabs} value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="arena" leftSection={<IconChartBar size={16} />}>
              {t('model_arena.tab_arena')}
            </Tabs.Tab>
            <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
              {t('model_arena.tab_history')}
            </Tabs.Tab>
          </Tabs.List>
        </Tabs>

        <Paper
          className={styles.stage}
          data-remis-surface="surface"
          radius="lg"
          p={{ base: 'md', md: 'xl' }}
        >
          {loading && !run ? (
            <Group justify="center" py={80}><Loader /></Group>
          ) : activeTab === 'history' ? (
            <ArenaHistory
              t={t}
              runs={history}
              projects={bootstrap.projects}
              loading={historyLoading}
              onOpen={openHistoricalRun}
              onPreviewExport={loadPreview}
              onDelete={setDeleteTarget}
            />
          ) : stage === 0 ? (
            <ArenaSetup
              t={t}
              projects={bootstrap.projects}
              providers={bootstrap.providers}
              languages={bootstrap.languages}
              values={values}
              onChange={(patch) => setValues((current) => ({ ...current, ...patch }))}
              draft={run}
              loading={loading}
              onCreateDraft={createDraft}
              onResample={resample}
              onEditDraft={editDraft}
              onRequestStart={() => {
                setApprovalAction('start');
                setApproved(false);
                setApprovalOpen(true);
              }}
            />
          ) : stage === 1 ? (
            <ArenaRunStatus
              t={t}
              run={run}
              onRefresh={refreshRun}
              onRetryFailures={() => {
                setApprovalAction('retry');
                setApproved(false);
                setApprovalOpen(true);
              }}
              retrying={retrying}
            />
          ) : stage === 2 ? (
            <ArenaVoting
              key={run.run_id}
              t={t}
              run={run}
              votes={votes}
              saving={savingVote}
              onSaveVote={saveVote}
              onComplete={completeRun}
              onRetryFailures={() => {
                setApprovalAction('retry');
                setApproved(false);
                setApprovalOpen(true);
              }}
              retrying={retrying}
            />
          ) : (
            <ArenaResults
              t={t}
              run={run}
              onPreviewExport={loadPreview}
              onRetryFailures={() => {
                setApprovalAction('retry');
                setApproved(false);
                setApprovalOpen(true);
              }}
              retrying={retrying}
            />
          )}
        </Paper>
      </Stack>

      <Modal
        opened={approvalOpen}
        onClose={() => {
          setApprovalOpen(false);
          setApproved(false);
        }}
        title={t(
          approvalAction === 'retry'
            ? 'model_arena.retry_cost_title'
            : 'model_arena.cost_title',
        )}
        centered
        data-remis-surface="elevated"
        classNames={arenaModalClassNames}
      >
        <Stack>
          <Alert
            className={styles.costAlert}
            color="yellow"
            variant="light"
            icon={<IconShieldCheck size={18} />}
          >
            {t(
              approvalAction === 'retry'
                ? 'model_arena.retry_cost_description'
                : 'model_arena.cost_description',
              {
              models: approvalModelCount,
              samples: run?.sample_size || values.sample_size,
              calls: approvalRequestCount,
              },
            )}
          </Alert>
          <Text size="sm">{t('model_arena.cost_unknown')}</Text>
          <Checkbox
            checked={approved}
            onChange={(event) => setApproved(event.currentTarget.checked)}
            label={t('model_arena.cost_confirm')}
          />
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setApprovalOpen(false);
                setApproved(false);
              }}
            >
              {t('cancel')}
            </Button>
            <Button
              leftSection={<IconPlayerPlay size={17} />}
              disabled={!approved}
              loading={loading}
              onClick={approvalAction === 'retry' ? retryFailures : startRun}
            >
              {t(
                approvalAction === 'retry'
                  ? 'model_arena.confirm_retry'
                  : 'model_arena.confirm_start',
              )}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={t('model_arena.delete_title')}
        centered
        data-remis-surface="elevated"
        classNames={arenaModalClassNames}
      >
        <Stack>
          <Text>{t('model_arena.delete_description')}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>{t('cancel')}</Button>
            <Button color="red" onClick={deleteRun} loading={loading}>{t('model_arena.delete')}</Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(previewTarget)}
        onClose={() => { setPreviewTarget(null); setPreview(null); }}
        title={t('model_arena.preview_title')}
        size="xl"
        data-remis-surface="elevated"
        classNames={arenaModalClassNames}
      >
        <Stack>
          <SegmentedControl
            fullWidth
            value={previewMode}
            onChange={(mode) => loadPreview(previewTarget, mode)}
            data={[
              { value: 'evidence', label: t('model_arena.evidence') },
              { value: 'summary-only', label: t('model_arena.summary_only') },
            ]}
          />
          <Alert color="blue">{previewMode === 'evidence'
            ? t('model_arena.evidence_description')
            : t('model_arena.summary_description')}</Alert>
          {previewLoading ? (
            <Group justify="center" py="xl"><Loader /></Group>
          ) : (
            <Code block className={styles.jsonPreview}>
              {JSON.stringify(preview, null, 2)}
            </Code>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setPreviewTarget(null)}>{t('model_arena.close')}</Button>
            <Button
              leftSection={<IconShieldCheck size={17} />}
              disabled={!preview || previewLoading}
              onClick={exportRun}
            >
              {t('model_arena.export_confirmed')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Box>
  );
}
