import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Group, Paper, Select, Stack, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBook2, IconExternalLink, IconInfoCircle, IconLink, IconPlus, IconUnlink } from '@tabler/icons-react';

import api from '../../utils/api';

const API_BASE_URL = '/api';
const ALL_GAMES_FILTER = '__all__';

export default function ProjectGlossaryPanel({ project, t }) {
  const navigate = useNavigate();
  const [glossaries, setGlossaries] = useState([]);
  const [projectGlossary, setProjectGlossary] = useState(null);
  const [selectedGameId, setSelectedGameId] = useState(ALL_GAMES_FILTER);
  const [selectedGlossaryId, setSelectedGlossaryId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const loadGlossaryState = useCallback(async () => {
    if (!project?.project_id || !project?.game_id) return;
    setIsLoading(true);
    try {
      const [glossariesResponse, projectGlossaryResponse] = await Promise.all([
        api.get(`${API_BASE_URL}/glossaries`),
        api.get(`${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(project.project_id)}`),
      ]);
      const available = glossariesResponse.data || [];
      const current = projectGlossaryResponse.data || null;
      setGlossaries(available);
      setProjectGlossary(current);
      setSelectedGlossaryId(current?.glossary_id ? String(current.glossary_id) : '');
    } catch {
      notifications.show({
        title: t('project_management.project_glossary.load_failed_title'),
        message: t('project_management.project_glossary.load_failed_message'),
        color: 'red',
      });
    } finally {
      setIsLoading(false);
    }
  }, [project?.game_id, project?.project_id, t]);

  useEffect(() => {
    loadGlossaryState();
  }, [loadGlossaryState]);

  const gameOptions = useMemo(() => {
    const gameIds = Array.from(new Set(glossaries.map((glossary) => glossary.game_id).filter(Boolean))).sort();
    return [
      { value: ALL_GAMES_FILTER, label: t('project_management.project_glossary.all_games') },
      ...gameIds.map((gameId) => ({ value: gameId, label: gameId })),
    ];
  }, [glossaries, t]);

  const filteredGlossaries = useMemo(() => (
    selectedGameId === ALL_GAMES_FILTER
      ? glossaries
      : glossaries.filter((glossary) => glossary.game_id === selectedGameId)
  ), [glossaries, selectedGameId]);

  const glossaryOptions = useMemo(() => (
    filteredGlossaries
      .map((glossary) => {
        const badges = [
          glossary.game_id,
          glossary.is_main ? t('project_management.project_glossary.main_glossary_badge') : null,
        ].filter(Boolean).join(' / ');
        return {
          value: String(glossary.glossary_id),
          label: badges ? `${glossary.name} (${badges})` : glossary.name,
        };
      })
  ), [filteredGlossaries, t]);

  const selectedGlossary = glossaries.find((glossary) => String(glossary.glossary_id) === selectedGlossaryId);
  const hasBoundGlossary = Boolean(projectGlossary?.glossary_id && !projectGlossary?.pending_creation);

  const handleEnsureProjectGlossary = async () => {
    setIsSaving(true);
    try {
      const response = await api.post(`${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(project.project_id)}`);
      setProjectGlossary(response.data);
      setSelectedGameId(ALL_GAMES_FILTER);
      setSelectedGlossaryId(response.data?.glossary_id ? String(response.data.glossary_id) : '');
      await loadGlossaryState();
      notifications.show({
        title: t('project_management.project_glossary.create_success_title'),
        message: t('project_management.project_glossary.create_success_message'),
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: t('project_management.project_glossary.create_failed_title'),
        message: error.response?.data?.detail || t('project_management.project_glossary.create_failed_message'),
        color: 'red',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleBind = async () => {
    if (!selectedGlossaryId) return;
    setIsSaving(true);
    try {
      const response = await api.put(`${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(project.project_id)}`, {
        glossary_id: Number(selectedGlossaryId),
      });
      setProjectGlossary(response.data);
      notifications.show({
        title: t('project_management.project_glossary.bind_success_title'),
        message: t('project_management.project_glossary.bind_success_message'),
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: t('project_management.project_glossary.bind_failed_title'),
        message: error.response?.data?.detail || t('project_management.project_glossary.bind_failed_message'),
        color: 'red',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleUnbind = async () => {
    setIsSaving(true);
    try {
      await api.delete(`${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(project.project_id)}`);
      await loadGlossaryState();
      setSelectedGlossaryId('');
      notifications.show({
        title: t('project_management.project_glossary.unbind_success_title'),
        message: t('project_management.project_glossary.unbind_success_message'),
        color: 'gray',
      });
    } catch {
      notifications.show({
        title: t('project_management.project_glossary.unbind_failed_title'),
        message: t('project_management.project_glossary.unbind_failed_message'),
        color: 'red',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenGlossary = () => {
    const glossaryId = projectGlossary?.glossary_id || selectedGlossary?.glossary_id;
    const glossaryGameId = projectGlossary?.game_id || selectedGlossary?.game_id || project.game_id;
    if (!glossaryId) return;
    navigate(`/glossary-manager?game_id=${encodeURIComponent(glossaryGameId)}&glossary_id=${encodeURIComponent(glossaryId)}`);
  };

  return (
    <Stack gap="md">
      <Paper p="lg" withBorder>
        <Stack gap="sm">
          <Group justify="space-between" align="flex-start">
            <div>
              <Title order={3}>{t('project_management.project_glossary.title')}</Title>
              <Text c="dimmed" size="sm" maw={760}>
                {t('project_management.project_glossary.description')}
              </Text>
            </div>
            {hasBoundGlossary && (
              <Badge color="teal" variant="light" leftSection={<IconBook2 size={12} />}>
                {projectGlossary.name}
              </Badge>
            )}
          </Group>

          <Alert icon={<IconInfoCircle size={18} />} color="blue" variant="light">
            {t('project_management.project_glossary.auto_binding_note')}
          </Alert>
        </Stack>
      </Paper>

      <Paper p="lg" withBorder>
        <Stack gap="md">
          <div>
            <Text fw={700}>{t('project_management.project_glossary.current_binding')}</Text>
            <Text size="sm" c="dimmed">
              {hasBoundGlossary
                ? t('project_management.project_glossary.bound_to', { name: projectGlossary.name })
                : t('project_management.project_glossary.not_bound')}
            </Text>
          </div>

          <Select
            label={t('project_management.project_glossary.game_filter_label')}
            placeholder={t('project_management.project_glossary.game_filter_placeholder')}
            data={gameOptions}
            value={selectedGameId}
            onChange={(value) => {
              setSelectedGameId(value || ALL_GAMES_FILTER);
              setSelectedGlossaryId('');
            }}
            disabled={isLoading || isSaving}
            allowDeselect={false}
            searchable
          />

          <Select
            label={t('project_management.project_glossary.select_label')}
            placeholder={t('project_management.project_glossary.select_placeholder')}
            data={glossaryOptions}
            value={selectedGlossaryId}
            onChange={setSelectedGlossaryId}
            disabled={isLoading || isSaving}
            searchable
            clearable
          />

          <Group>
            <Button
              leftSection={<IconLink size={16} />}
              onClick={handleBind}
              disabled={!selectedGlossaryId}
              loading={isSaving}
            >
              {t('project_management.project_glossary.bind_button')}
            </Button>
            <Button
              leftSection={<IconPlus size={16} />}
              variant="light"
              onClick={handleEnsureProjectGlossary}
              loading={isSaving}
            >
              {t('project_management.project_glossary.create_button')}
            </Button>
            <Button
              leftSection={<IconUnlink size={16} />}
              variant="light"
              color="gray"
              onClick={handleUnbind}
              disabled={!hasBoundGlossary}
              loading={isSaving}
            >
              {t('project_management.project_glossary.unbind_button')}
            </Button>
            <Button
              leftSection={<IconExternalLink size={16} />}
              variant="outline"
              onClick={handleOpenGlossary}
              disabled={!hasBoundGlossary && !selectedGlossary}
            >
              {t('project_management.project_glossary.inspect_button')}
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Stack>
  );
}
