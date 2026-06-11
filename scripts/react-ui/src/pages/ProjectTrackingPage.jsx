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
  IconPlayerPlay,
  IconPlus,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react';
import { open } from '@tauri-apps/plugin-dialog';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PROJECT_WATCHES_UPDATED_EVENT } from '../components/ProjectWatchScheduler';
import projectService from '../services/projectService';
import projectWatchService from '../services/projectWatchService';

const PAGE_REFRESH_INTERVAL_MS = 60 * 1000;

const emptyForm = {
  name: '',
  path: '',
  project_id: '',
  enabled: true,
  scan_interval_minutes: 30,
};

const labels = {
  zh: {
    title: '项目追踪',
    subtitle: '追踪 Steam 或本地工具已经更新到硬盘上的 Mod 本地化目录，然后手动跳转到增量更新。',
    add: '添加追踪',
    edit: '编辑追踪',
    scanSelected: '扫描选中项',
    refresh: '刷新',
    empty: '还没有追踪路径。',
    path: '路径',
    project: '关联项目',
    status: '状态',
    lastScan: '最后扫描',
    changes: '变更',
    interval: '定时扫描',
    actions: '操作',
    name: '名称',
    enabled: '启用',
    minutes: '分钟',
    save: '保存',
    cancel: '取消',
    browse: '浏览',
    unlinked: '未关联',
    startIncremental: '开始增量更新',
    baseline: '已建立基线',
    clean: '无变更',
    changed: '有变更',
    never: '未扫描',
    never_scanned: '未扫描',
    no_localization: '没有本地化文件',
    scannedFiles: '已扫描文件',
    scanResult: '扫描完成',
    scanNow: '扫描',
    delete: '删除',
    selectProjectFirst: '这个追踪项还没有关联项目，无法跳转到增量更新。',
  },
  en: {
    title: 'Project Tracking',
    subtitle: 'Track Mod localization folders that Steam or local tools have already updated on disk, then jump into incremental update manually.',
    add: 'Add Watch',
    edit: 'Edit Watch',
    scanSelected: 'Scan Selected',
    refresh: 'Refresh',
    empty: 'No watched paths yet.',
    path: 'Path',
    project: 'Linked Project',
    status: 'Status',
    lastScan: 'Last Scan',
    changes: 'Changes',
    interval: 'Scheduled Scan',
    actions: 'Actions',
    name: 'Name',
    enabled: 'Enabled',
    minutes: 'minutes',
    save: 'Save',
    cancel: 'Cancel',
    browse: 'Browse',
    unlinked: 'Unlinked',
    startIncremental: 'Start Incremental Update',
    baseline: 'Baseline created',
    clean: 'Clean',
    changed: 'Changed',
    never: 'Never scanned',
    never_scanned: 'Never scanned',
    no_localization: 'No localization files',
    scannedFiles: 'Scanned files',
    scanResult: 'Scan complete',
    scanNow: 'Scan',
    delete: 'Delete',
    selectProjectFirst: 'This watch is not linked to a project, so it cannot jump into incremental update.',
  },
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

const ProjectTrackingPage = () => {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const text = (i18n?.language || '').toLowerCase().startsWith('zh') ? labels.zh : labels.en;
  const [watches, setWatches] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingWatch, setEditingWatch] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

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
      scan_interval_minutes: watch.scan_interval_minutes || 30,
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
      ...form,
      project_id: form.project_id || null,
      scan_interval_minutes: Number(form.scan_interval_minutes) || null,
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
    try {
      const response = await projectWatchService.scanWatches(watchIds);
      const results = Array.isArray(response.data) ? response.data : [];
      if (results.length === 1) {
        const result = results[0];
        const changedCount = result.changed_count ?? 0;
        setMessage(`${text.scanResult}: ${text[result.status] || result.status}, ${text.scannedFiles} ${result.scanned_file_count ?? 0}, ${text.changes} ${changedCount}. ${result.root_path || ''}`);
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
            <Text size="sm" c="dimmed" maw={760}>{text.subtitle}</Text>
          </div>
          <Group>
            <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={loadData} disabled={busy}>
              {text.refresh}
            </Button>
            <Button leftSection={<IconPlus size={16} />} onClick={openCreateModal}>
              {text.add}
            </Button>
          </Group>
        </Group>

        {message && <Alert color="orange" icon={<IconAlertTriangle size={16} />}>{message}</Alert>}

        <Paper withBorder radius="md" p="md">
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
            <Table striped highlightOnHover withTableBorder>
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
                          {watch.enabled && watch.scan_interval_minutes ? `${watch.scan_interval_minutes} ${text.minutes}` : '-'}
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
          <Group align="flex-end">
            <TextInput
              label={text.path}
              aria-label={text.path}
              value={form.path}
              onChange={(valueOrEvent) => updateFormField('path', valueOrEvent)}
              style={{ flex: 1 }}
              required
            />
            <Button variant="light" leftSection={<IconFolder size={16} />} onClick={browseFolder}>{text.browse}</Button>
          </Group>
          <Select
            label={text.project}
            data={projectOptions}
            value={form.project_id}
            onChange={(value) => setForm((current) => ({ ...current, project_id: value || '' }))}
          />
          <Group grow align="flex-end">
            <Switch
              label={text.enabled}
              checked={form.enabled}
              onChange={(valueOrEvent) => updateFormCheckedField('enabled', valueOrEvent)}
            />
            <NumberInput
              label={text.interval}
              min={1}
              value={form.scan_interval_minutes}
              onChange={(value) => setForm((current) => ({ ...current, scan_interval_minutes: value || 30 }))}
              suffix={` ${text.minutes}`}
            />
          </Group>
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
