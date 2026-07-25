import React, { useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Modal,
  NumberInput,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconEdit,
  IconFolder,
  IconHistory,
  IconPlayerPlay,
  IconPlus,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react';
import { open } from '@tauri-apps/plugin-dialog';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PROJECT_WATCHES_UPDATED_EVENT } from '../components/ProjectWatchScheduler';
import { useTutorial } from '../context/TutorialContextCore';
import projectService from '../services/projectService';
import projectWatchService from '../services/projectWatchService';
import { taskDetailRoute } from '../utils/taskRoutes';
import styles from './ProjectTrackingPage.module.css';

const PAGE_REFRESH_INTERVAL_MS = 60 * 1000;

const emptyForm = {
  name: '',
  path: '',
  project_id: '',
  enabled: true,
  scan_interval_value: 30,
  scan_interval_unit: 'minutes',
};

const statusColor = {
  changed: 'orange',
  clean: 'green',
  baseline: 'blue',
  never_scanned: 'gray',
  no_localization: 'red',
};

const readInputValue = (valueOrEvent) => {
  if (valueOrEvent && typeof valueOrEvent === 'object' && 'currentTarget' in valueOrEvent) {
    return valueOrEvent.currentTarget?.value ?? '';
  }
  return valueOrEvent ?? '';
};

const readCheckedValue = (valueOrEvent) => {
  if (valueOrEvent && typeof valueOrEvent === 'object' && 'currentTarget' in valueOrEvent) {
    return Boolean(valueOrEvent.currentTarget?.checked);
  }
  return Boolean(valueOrEvent);
};

const intervalUnitToMinutes = {
  minutes: 1,
  hours: 60,
  days: 60 * 24,
};

const toScanIntervalMinutes = (value, unit) => {
  const numericValue = Number(value) || 1;
  return numericValue * (intervalUnitToMinutes[unit] || 1);
};

const fromScanIntervalMinutes = (minutes = 30) => {
  if (minutes % intervalUnitToMinutes.days === 0) {
    return { scan_interval_value: minutes / intervalUnitToMinutes.days, scan_interval_unit: 'days' };
  }
  if (minutes % intervalUnitToMinutes.hours === 0) {
    return { scan_interval_value: minutes / intervalUnitToMinutes.hours, scan_interval_unit: 'hours' };
  }
  return { scan_interval_value: minutes, scan_interval_unit: 'minutes' };
};

const ProjectTrackingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setPageContext } = useTutorial();
  const [watches, setWatches] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingWatch, setEditingWatch] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [scanFeedback, setScanFeedback] = useState(null);

  useEffect(() => {
    setPageContext(modalOpen ? 'project-tracking-modal' : 'project-tracking');
  }, [modalOpen, setPageContext]);

  const text = useMemo(() => ({
    title: t('project_tracking.title'),
    subtitle: t('project_tracking.subtitle'),
    add: t('project_tracking.add_new_project'),
    edit: t('project_tracking.edit'),
    scanSelected: t('project_tracking.scan_selected'),
    refresh: t('project_tracking.refresh'),
    empty: t('project_tracking.empty'),
    path: t('project_tracking.path'),
    project: t('project_tracking.project'),
    status: t('project_tracking.status'),
    lastScan: t('project_tracking.last_scan'),
    changes: t('project_tracking.changes'),
    interval: t('project_tracking.interval'),
    actions: t('project_tracking.actions'),
    name: t('project_tracking.name'),
    enabled: t('project_tracking.enabled'),
    save: t('project_tracking.save'),
    cancel: t('project_tracking.cancel'),
    browse: t('project_tracking.browse'),
    unlinked: t('project_tracking.unlinked'),
    startIncremental: t('project_tracking.start_incremental'),
    baseline: t('project_tracking.status_baseline'),
    clean: t('project_tracking.status_clean'),
    changed: t('project_tracking.status_changed'),
    never: t('project_tracking.status_never'),
    never_scanned: t('project_tracking.status_never'),
    no_localization: t('project_tracking.status_no_localization'),
    scannedFiles: t('project_tracking.scanned_files'),
    scanResult: t('project_tracking.scan_result'),
    scanNow: t('project_tracking.scan_now'),
    delete: t('project_tracking.delete'),
    pathDescription: t('project_tracking.path_description'),
    safetyDescription: t('project_tracking.path_safety_description'),
    projectDescription: t('project_tracking.project_description'),
    enabledDescription: t('project_tracking.enabled_description'),
    intervalUnit: t('project_tracking.interval_unit'),
    units: {
      minutes: t('project_tracking.unit_minutes'),
      hours: t('project_tracking.unit_hours'),
      days: t('project_tracking.unit_days'),
    },
    selectProjectFirst: t('project_tracking.select_project_first'),
    viewScanTask: t('task_center.view_task'),
  }), [t]);

  const intervalUnitOptions = useMemo(() => [
    { value: 'minutes', label: text.units.minutes },
    { value: 'hours', label: text.units.hours },
    { value: 'days', label: text.units.days },
  ], [text.units.days, text.units.hours, text.units.minutes]);

  const updateFormField = (field, valueOrEvent) => {
    const nextValue = readInputValue(valueOrEvent);
    setForm((current) => ({
      ...current,
      [field]: nextValue,
    }));
  };

  const updateFormCheckedField = (field, valueOrEvent) => {
    const nextValue = readCheckedValue(valueOrEvent);
    setForm((current) => ({
      ...current,
      [field]: nextValue,
    }));
  };

  const projectOptions = useMemo(() => [
    { value: '', label: text.unlinked },
    ...projects.map((project) => ({
      value: project.project_id,
      label: `${project.name} (${project.game_id})`,
    })),
  ], [projects, text.unlinked]);

  const projectById = useMemo(() => new Map(projects.map((project) => [project.project_id, project])), [projects]);

  const loadData = async () => {
    const [watchRes, projectRes] = await Promise.all([
      projectWatchService.listWatches(),
      projectService.getActiveProjects(),
    ]);
    setWatches(Array.isArray(watchRes.data) ? watchRes.data : []);
    setProjects(Array.isArray(projectRes.data) ? projectRes.data : []);
  };

  const refreshWatches = async () => {
    const watchRes = await projectWatchService.listWatches();
    setWatches(Array.isArray(watchRes.data) ? watchRes.data : []);
  };

  useEffect(() => {
    loadData().catch((error) => {
      console.error('Failed to load project tracking data:', error);
      setMessage(error.response?.data?.detail || error.message);
    });
  }, []);

  useEffect(() => {
    const refresh = () => {
      refreshWatches().catch((error) => {
        console.warn('Failed to refresh project watches:', error);
      });
    };
    const timer = window.setInterval(refresh, PAGE_REFRESH_INTERVAL_MS);
    window.addEventListener(PROJECT_WATCHES_UPDATED_EVENT, refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(PROJECT_WATCHES_UPDATED_EVENT, refresh);
    };
  }, []);

  const openCreateModal = () => {
    setEditingWatch(null);
    setForm(emptyForm);
    setModalOpen(true);
  };

  const openEditModal = (watch) => {
    setEditingWatch(watch);
    setForm({
      name: watch.name || '',
      path: watch.path || '',
      project_id: watch.project_id || '',
      enabled: Boolean(watch.enabled),
      ...fromScanIntervalMinutes(watch.scan_interval_minutes || 30),
    });
    setModalOpen(true);
  };

  const browseFolder = async () => {
    const selected = await open({ directory: true, multiple: false, title: text.path });
    if (selected && typeof selected === 'string') {
      setForm((current) => ({ ...current, path: selected }));
    }
  };

  const saveWatch = async () => {
    setBusy(true);
    setMessage('');
    const payload = {
      name: form.name,
      path: form.path,
      project_id: form.project_id || null,
      enabled: form.enabled,
      scan_interval_minutes: form.enabled
        ? toScanIntervalMinutes(form.scan_interval_value, form.scan_interval_unit)
        : null,
    };
    try {
      if (editingWatch) {
        await projectWatchService.updateWatch(editingWatch.watch_id, payload);
      } else {
        await projectWatchService.createWatch(payload);
      }
      setModalOpen(false);
      await loadData();
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteWatch = async (watchId) => {
    setBusy(true);
    try {
      await projectWatchService.deleteWatch(watchId);
      setSelectedIds((ids) => ids.filter((id) => id !== watchId));
      await loadData();
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setBusy(false);
    }
  };

  const scanWatches = async (watchIds) => {
    if (!watchIds.length) return;
    setBusy(true);
    setMessage('');
    setScanFeedback(null);
    try {
      const response = await projectWatchService.scanWatches(watchIds);
      const results = Array.isArray(response.data) ? response.data : [];
      const blockedOrFailed = results.find((result) => ['blocked', 'failed'].includes(result.status));
      if (blockedOrFailed?.message) {
        setMessage(blockedOrFailed.message);
      }
      if (results.length === 1) {
        const result = results[0];
        if (!blockedOrFailed) {
          const changedCount = result.changed_count ?? 0;
          setScanFeedback({
            summary: t('project_tracking.scan_message', {
              status: text[result.status] || result.status,
              scanned: result.scanned_file_count ?? 0,
              changes: changedCount,
              path: '',
            }).trim(),
            rootPath: result.root_path || '',
            taskId: result.task_id || '',
          });
        }
      }
      await loadData();
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleSelected = (watchId, checked) => {
    setSelectedIds((ids) => checked ? [...new Set([...ids, watchId])] : ids.filter((id) => id !== watchId));
  };

  const startIncrementalUpdate = (watch) => {
    const project = projectById.get(watch.project_id);
    if (!project) {
      setMessage(text.selectProjectFirst);
      return;
    }
    navigate('/incremental-translation', {
      state: {
        projectId: watch.project_id,
        customSourcePath: watch.path,
        fromProjectWatch: true,
      },
    });
  };

  const renderStatus = (watch) => {
    const status = watch.status || 'never_scanned';
    const label = text[status] || status;
    return <Badge color={statusColor[status] || 'gray'} variant="light">{label}</Badge>;
  };

  const formatInterval = (minutes) => {
    const interval = fromScanIntervalMinutes(minutes || 30);
    return `${interval.scan_interval_value} ${text.units[interval.scan_interval_unit]}`;
  };

  const renderChangedCount = (watch) => {
    const summary = watch.last_scan_summary || {};
    const count = summary.changed_count || 0;
    if (watch.status === 'no_localization') {
      return <Text size="sm" c="red">{text.no_localization}</Text>;
    }
    if (!count) return <Text size="sm" c="dimmed">0</Text>;
    return (
      <Group gap={6}>
        <IconAlertTriangle size={16} color="orange" />
        <Text size="sm" fw={700}>{count}</Text>
      </Group>
    );
  };

  return (
    <Container fluid p="lg" h="100%" style={{ overflow: 'auto' }}>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={2}>{text.title}</Title>
            <Text size="sm" maw={760} className={styles.pageSubtitle}>{text.subtitle}</Text>
          </div>
          <Group>
            <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={loadData} disabled={busy}>
              {text.refresh}
            </Button>
            <Button id="project-tracking-add-btn" leftSection={<IconPlus size={16} />} onClick={openCreateModal}>
              {text.add}
            </Button>
          </Group>
        </Group>

        {message && (
          <Alert color="orange" icon={<IconAlertTriangle size={16} />} data-remis-surface="paper">
            {message}
          </Alert>
        )}
        {scanFeedback && (
          <Paper withBorder radius="md" p="md" data-remis-surface="paper">
            <Stack gap="xs">
              <Group justify="space-between" align="flex-start">
                <Text fw={700}>{scanFeedback.summary}</Text>
                {scanFeedback.taskId && (
                  <Button
                    variant="subtle"
                    size="compact-sm"
                    onClick={() => navigate(taskDetailRoute(scanFeedback.taskId))}
                  >
                    {text.viewScanTask}
                  </Button>
                )}
              </Group>
              {scanFeedback.rootPath && (
                <Text
                  data-testid="project-tracking-scan-path"
                  c="dimmed"
                  style={{
                    fontFamily: 'monospace',
                    fontSize: 'var(--mantine-font-size-xs)',
                    overflowWrap: 'anywhere',
                  }}
                >
                  {scanFeedback.rootPath}
                </Text>
              )}
            </Stack>
          </Paper>
        )}

        <Paper withBorder radius="md" p="md" className={styles.trackingSurface}>
          <Group justify="space-between" mb="md">
            <Group>
              <Checkbox
                checked={watches.length > 0 && selectedIds.length === watches.length}
                indeterminate={selectedIds.length > 0 && selectedIds.length < watches.length}
                onChange={(event) => setSelectedIds(event.currentTarget.checked ? watches.map((watch) => watch.watch_id) : [])}
              />
              <Text size="sm" c="dimmed">{selectedIds.length} / {watches.length}</Text>
            </Group>
            <Button
              id="project-tracking-scan-selected-btn"
              variant="light"
              leftSection={<IconRefresh size={16} />}
              disabled={!selectedIds.length || busy}
              onClick={() => scanWatches(selectedIds)}
            >
              {text.scanSelected}
            </Button>
          </Group>

          {watches.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">{text.empty}</Text>
          ) : (
            <Table id="project-tracking-table" striped highlightOnHover withTableBorder className={styles.trackingTable}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th />
                  <Table.Th>{text.name}</Table.Th>
                  <Table.Th>{text.path}</Table.Th>
                  <Table.Th>{text.project}</Table.Th>
                  <Table.Th>{text.status}</Table.Th>
                  <Table.Th>{text.changes}</Table.Th>
                  <Table.Th>{text.interval}</Table.Th>
                  <Table.Th>{text.lastScan}</Table.Th>
                  <Table.Th>{text.actions}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {watches.map((watch) => {
                  const project = projectById.get(watch.project_id);
                  return (
                    <Table.Tr key={watch.watch_id}>
                      <Table.Td>
                        <Checkbox
                          checked={selectedIds.includes(watch.watch_id)}
                          onChange={(event) => toggleSelected(watch.watch_id, event.currentTarget.checked)}
                        />
                      </Table.Td>
                      <Table.Td><Text fw={600}>{watch.name}</Text></Table.Td>
                      <Table.Td><Text size="xs" lineClamp={2}>{watch.path}</Text></Table.Td>
                      <Table.Td>{project ? project.name : <Text size="sm" c="dimmed">{text.unlinked}</Text>}</Table.Td>
                      <Table.Td>{renderStatus(watch)}</Table.Td>
                      <Table.Td>
                        <Stack gap={2}>
                          {renderChangedCount(watch)}
                          {watch.last_scan_summary?.scanned_file_count !== undefined && (
                            <Text size="xs" c="dimmed">
                              {text.scannedFiles}: {watch.last_scan_summary.scanned_file_count}
                            </Text>
                          )}
                        </Stack>
                      </Table.Td>
                      <Table.Td>
                        <Badge color={watch.enabled ? 'teal' : 'gray'} variant="light">
                          {watch.enabled && watch.scan_interval_minutes ? formatInterval(watch.scan_interval_minutes) : '-'}
                        </Badge>
                      </Table.Td>
                      <Table.Td><Text size="xs">{watch.last_scan_at ? new Date(watch.last_scan_at).toLocaleString() : '-'}</Text></Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          <Tooltip label={text.scanNow}>
                            <ActionIcon aria-label={text.scanNow} variant="subtle" onClick={() => scanWatches([watch.watch_id])} disabled={busy}>
                              <IconRefresh size={16} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label={text.startIncremental}>
                            <ActionIcon aria-label={text.startIncremental} variant="subtle" color="green" onClick={() => startIncrementalUpdate(watch)}>
                              <IconPlayerPlay size={16} />
                            </ActionIcon>
                          </Tooltip>
                          {watch.last_scan_summary?.task_id && (
                            <Tooltip label={text.viewScanTask}>
                              <ActionIcon
                                aria-label={text.viewScanTask}
                                variant="subtle"
                                color="blue"
                                onClick={() => navigate(taskDetailRoute(watch.last_scan_summary.task_id))}
                              >
                                <IconHistory size={16} />
                              </ActionIcon>
                            </Tooltip>
                          )}
                          <Tooltip label={text.edit}>
                            <ActionIcon aria-label={text.edit} variant="subtle" onClick={() => openEditModal(watch)}>
                              <IconEdit size={16} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label={text.delete}>
                            <ActionIcon aria-label={text.delete} variant="subtle" color="red" onClick={() => deleteWatch(watch.watch_id)} disabled={busy}>
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={editingWatch ? text.edit : text.add} size="lg">
        <Stack>
          <TextInput
            label={text.name}
            aria-label={text.name}
            value={form.name}
            onChange={(valueOrEvent) => updateFormField('name', valueOrEvent)}
            required
          />
          <Stack id="project-tracking-path-field" gap={6}>
            <Group align="flex-end">
              <TextInput
                label={text.path}
                aria-label={text.path}
                value={form.path}
                onChange={(valueOrEvent) => updateFormField('path', valueOrEvent)}
                description={text.pathDescription}
                style={{ flex: 1 }}
                required
              />
              <Button variant="light" leftSection={<IconFolder size={16} />} onClick={browseFolder}>{text.browse}</Button>
            </Group>
            <Text size="xs" c="dimmed">{text.safetyDescription}</Text>
          </Stack>
          <Stack id="project-tracking-linked-project-field" gap={4}>
            <Select
              label={text.project}
              description={text.projectDescription}
              data={projectOptions}
              value={form.project_id}
              onChange={(value) => setForm((current) => ({ ...current, project_id: value || '' }))}
            />
          </Stack>
          <Stack id="project-tracking-schedule-field" gap={8}>
            <Switch
              label={text.enabled}
              description={text.enabledDescription}
              checked={form.enabled}
              onChange={(valueOrEvent) => updateFormCheckedField('enabled', valueOrEvent)}
            />
            {form.enabled && (
              <Group grow align="flex-end">
                <NumberInput
                  label={text.interval}
                  min={1}
                  value={form.scan_interval_value}
                  onChange={(value) => setForm((current) => ({ ...current, scan_interval_value: value || 1 }))}
                />
                <Select
                  label={text.intervalUnit}
                  data={intervalUnitOptions}
                  value={form.scan_interval_unit}
                  onChange={(value) => setForm((current) => ({ ...current, scan_interval_unit: value || 'minutes' }))}
                />
              </Group>
            )}
          </Stack>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setModalOpen(false)}>{text.cancel}</Button>
            <Button onClick={saveWatch} loading={busy} disabled={!form.name || !form.path}>{text.save}</Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
};

export default ProjectTrackingPage;
