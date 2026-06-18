import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Grid, Paper, Title, Text, Stack, Group, Button,
    TextInput, ScrollArea, Badge, ActionIcon, LoadingOverlay, Box,
    ThemeIcon, Select
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
    IconCheck, IconX, IconBulb, IconQuote,
    IconGavel, IconSparkles
} from '@tabler/icons-react';
import api from '../../utils/api';

const API_BASE_URL = '/api';

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * 新词审核法庭组件
 * 负责审核和批准 AI 挖掘的新词候选
 */
const JudgmentCourt = () => {
    const { t } = useTranslation();
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [candidates, setCandidates] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [editSuggestion, setEditSuggestion] = useState("");
    const [glossaries, setGlossaries] = useState([]);
    const [selectedGlossaryId, setSelectedGlossaryId] = useState(null);

    useEffect(() => {
        if (selectedId) {
            const candidate = candidates.find(c => c.id === selectedId);
            if (candidate) {
                setEditSuggestion(candidate.suggestion || "");
            }
        }
    }, [selectedId, candidates]);

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            setProjects(response.data);
            if (response.data.length > 0) {
                setSelectedProject(response.data[0].project_id);
            }
        } catch (error) {
            console.error("Failed to fetch projects", error);
        }
    }, []);

    const fetchCandidates = useCallback(async (projectId) => {
        setLoading(true);
        try {
            const response = await api.get(`${API_BASE_URL}/neologisms?project_id=${projectId}`);
            setCandidates(response.data);
            setSelectedId(prev => prev || response.data[0]?.id || null);
        } catch {
            notifications.show({ title: 'Error', message: 'Failed to load candidates', color: 'red' });
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchGlossaries = useCallback(async (project) => {
        if (!project?.game_id) {
            setGlossaries([]);
            setSelectedGlossaryId(null);
            return;
        }

        try {
            const response = await api.get(`${API_BASE_URL}/glossaries/${encodeURIComponent(project.game_id)}`);
            const nextGlossaries = response.data || [];
            setGlossaries(nextGlossaries);
            const mainGlossary = nextGlossaries.find((glossary) => glossary.is_main);
            setSelectedGlossaryId(String((mainGlossary || nextGlossaries[0])?.glossary_id || ''));
        } catch {
            setGlossaries([]);
            setSelectedGlossaryId(null);
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.glossary_load_failed'),
                color: 'red'
            });
        }
    }, [t]);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    useEffect(() => {
        if (selectedProject) {
            fetchCandidates(selectedProject);
            fetchGlossaries(projects.find(p => p.project_id === selectedProject));
        } else {
            setCandidates([]);
            setGlossaries([]);
            setSelectedGlossaryId(null);
        }
    }, [fetchCandidates, fetchGlossaries, projects, selectedProject]);

    const handleApprove = async () => {
        if (!selectedId || !selectedProject || !selectedGlossaryId) return;
        const candidate = candidates.find(c => c.id === selectedId);
        if (!candidate) return;

        setProcessing(true);
        try {
            await api.post(`${API_BASE_URL}/neologisms/${selectedId}/approve`, {
                project_id: selectedProject,
                final_translation: editSuggestion,
                glossary_id: Number(selectedGlossaryId),
                source_lang: candidate.source_lang || currentProject?.source_language || 'en',
                target_lang: candidate.target_lang || 'zh-CN'
            });
            notifications.show({
                title: t('neologism_review.court.approved_title'),
                message: t('neologism_review.court.approved_message'),
                color: 'green'
            });
            removeCandidate(selectedId);
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.approve_failed'),
                color: 'red'
            });
        } finally {
            setProcessing(false);
        }
    };

    const handleReject = async () => {
        if (!selectedId || !selectedProject) return;
        setProcessing(true);
        try {
            await api.post(`${API_BASE_URL}/neologisms/${selectedId}/reject`, {
                project_id: selectedProject
            });
            notifications.show({
                title: t('neologism_review.court.rejected_title'),
                message: t('neologism_review.court.rejected_message'),
                color: 'gray'
            });
            removeCandidate(selectedId);
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.reject_failed'),
                color: 'red'
            });
        } finally {
            setProcessing(false);
        }
    };

    const removeCandidate = (id) => {
        const newList = candidates.filter(c => c.id !== id);
        setCandidates(newList);
        if (newList.length > 0) {
            setSelectedId(newList[0].id);
        } else {
            setSelectedId(null);
        }
    };

    const selectedCandidate = candidates.find(c => c.id === selectedId);
    const currentProject = projects.find(p => p.project_id === selectedProject);

    const HighlightedText = ({ text, term }) => {
        if (!text || !term) return <Text>{text}</Text>;
        const parts = text.split(new RegExp(`(${escapeRegExp(term)})`, 'gi'));
        return (
            <Text size="sm" c="dimmed" lh={1.6}>
                {parts.map((part, i) =>
                    part.toLowerCase() === term.toLowerCase() ?
                        <span key={i} style={{
                            color: 'var(--mantine-color-yellow-4)',
                            fontWeight: 'bold',
                            backgroundColor: 'rgba(255, 255, 0, 0.1)',
                            padding: '0 4px',
                            borderRadius: '4px'
                        }}>{part}</span> :
                        part
                )}
            </Text>
        );
    };

    return (
        <Box h="100%" style={{ display: 'flex', flexDirection: 'column' }}>
            {/* Project Context Header */}
            <Paper p="md" mb="md" style={{ background: 'var(--glass-bg)', borderBottom: '1px solid var(--glass-border)' }}>
                <Group justify="space-between" align="center">
                    <Box style={{ flex: 1 }}>
                        <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>{t('neologism_review.court.current_project')}</Text>
                        <Select
                            data={projects.map(p => ({ value: p.project_id, label: p.name }))}
                            value={selectedProject}
                            onChange={setSelectedProject}
                            placeholder={t('neologism_review.court.select_project')}
                            size="md"
                            mt="xs"
                        />
                        <Select
                            data={glossaries.map((glossary) => ({
                                value: String(glossary.glossary_id),
                                label: glossary.is_main ? `${glossary.name} (${t('neologism_review.court.main_glossary')})` : glossary.name,
                            }))}
                            value={selectedGlossaryId}
                            onChange={setSelectedGlossaryId}
                            label={t('neologism_review.court.target_glossary')}
                            placeholder={t('neologism_review.court.select_glossary')}
                            size="sm"
                            mt="sm"
                        />
                    </Box>
                    {currentProject && (
                        <Badge size="lg" variant="light" color="blue">
                            {t('neologism_review.court.pending_terms', { count: candidates.length })}
                        </Badge>
                    )}
                </Group>
            </Paper>

            <Grid h="100%" gutter={0} style={{ flex: 1, overflow: 'hidden' }}>
                {/* Sidebar List */}
                <Grid.Col span={3} h="100%" style={{ borderRight: '1px solid var(--glass-border)', display: 'flex', flexDirection: 'column' }}>
                    <Stack p="md" h="100%">
                        <Group justify="space-between">
                            <Title order={4} c="dimmed">{t('neologism_review.court.docket')}</Title>
                            <Badge variant="dot" size="lg">{candidates.length}</Badge>
                        </Group>
                        <ScrollArea style={{ flex: 1, margin: '0 -16px' }} p="md">
                            <Stack gap="xs">
                                {candidates.map(c => (
                                    <Paper
                                        key={c.id}
                                        p="md"
                                        radius="md"
                                        onClick={() => setSelectedId(c.id)}
                                        style={{
                                            cursor: 'pointer',
                                            backgroundColor: selectedId === c.id ? 'var(--mantine-color-blue-light)' : 'var(--glass-bg)',
                                            border: selectedId === c.id ? '1px solid var(--mantine-color-blue-filled)' : '1px solid transparent',
                                            transition: 'all 0.2s ease'
                                        }}
                                    >
                                        <Text fw={600} lineClamp={1}>{c.original}</Text>
                                        <Text size="xs" c="dimmed" truncate>{c.suggestion}</Text>
                                    </Paper>
                                ))}
                                {candidates.length === 0 && !loading && (
                                    <Stack align="center" mt="xl" c="dimmed">
                                        <IconCheck size={32} />
                                        <Text>{t('neologism_review.court.caught_up')}</Text>
                                    </Stack>
                                )}
                            </Stack>
                        </ScrollArea>
                    </Stack>
                </Grid.Col>

                {/* Main Review Area */}
                <Grid.Col span={9} h="100%" style={{ position: 'relative' }}>
                    {selectedCandidate ? (
                        <Stack h="100%" p="xl" gap="xl">
                            <LoadingOverlay visible={processing} />

                            {/* Header Section */}
                            <Paper p="xl" radius="lg" style={{ background: 'var(--glass-bg)', backdropFilter: 'blur(10px)' }}>
                                <Group align="flex-start" justify="space-between">
                                    <Box>
                                        <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>{t('neologism_review.court.candidate_term')}</Text>
                                        <Title order={1} style={{ fontSize: '2.5rem', color: 'var(--mantine-color-blue-3)' }}>
                                            {selectedCandidate.original}
                                        </Title>
                                    </Box>
                                    <Badge size="lg" variant="outline" color="gray">
                                        {selectedCandidate.source_file.split('\\').pop()}
                                    </Badge>
                                </Group>
                            </Paper>

                            <Grid gutter="xl" style={{ flex: 1 }}>
                                {/* Left Column: Analysis & Action */}
                                <Grid.Col span={7}>
                                    <Stack gap="lg" h="100%">
                                        <Paper p="lg" radius="md" style={{ background: 'rgba(0,0,0,0.2)' }} withBorder>
                                            <Group mb="sm">
                                                <ThemeIcon color="yellow" variant="light" size="lg"><IconBulb size={20} /></ThemeIcon>
                                                <Text fw={700}>{t('neologism_review.court.ai_analysis')}</Text>
                                            </Group>
                                            <Text size="sm" style={{ lineHeight: 1.6 }}>
                                                {selectedCandidate.reasoning}
                                            </Text>
                                        </Paper>

                                        <Box mt="auto">
                                            <TextInput
                                                label={t('neologism_review.court.final_translation')}
                                                description={t('neologism_review.court.final_translation_desc')}
                                                size="xl"
                                                radius="md"
                                                value={editSuggestion}
                                                onChange={(e) => setEditSuggestion(e.currentTarget.value)}
                                                rightSection={
                                                    <ActionIcon variant="subtle" onClick={() => setEditSuggestion(selectedCandidate.suggestion)}>
                                                        <IconSparkles size={18} />
                                                    </ActionIcon>
                                                }
                                            />
                                            <Group mt="lg" grow>
                                                <Button
                                                    size="lg"
                                                    variant="default"
                                                    color="gray"
                                                    leftSection={<IconX />}
                                                    onClick={handleReject}
                                                >
                                                    {t('neologism_review.court.ignore')}
                                                </Button>
                                                <Button
                                                    size="lg"
                                                    variant="gradient"
                                                    gradient={{ from: 'teal', to: 'lime', deg: 105 }}
                                                    leftSection={<IconGavel />}
                                                    onClick={handleApprove}
                                                    disabled={!selectedGlossaryId}
                                                >
                                                    {t('neologism_review.court.approve')}
                                                </Button>
                                            </Group>
                                        </Box>
                                    </Stack>
                                </Grid.Col>

                                {/* Right Column: Evidence */}
                                <Grid.Col span={5}>
                                    <Stack h="100%">
                                        <Text fw={700} c="dimmed" tt="uppercase" size="xs">{t('neologism_review.court.context_evidence')}</Text>
                                        <ScrollArea style={{ flex: 1 }} type="auto">
                                            <Stack gap="sm">
                                                {selectedCandidate.context_snippets.map((snippet, idx) => (
                                                    <Paper key={idx} p="md" radius="md" style={{ background: 'rgba(0,0,0,0.3)' }}>
                                                        <Group align="flex-start" gap="xs" wrap="nowrap">
                                                            <IconQuote size={16} style={{ opacity: 0.5, marginTop: 4 }} />
                                                            <HighlightedText text={snippet} term={selectedCandidate.original} />
                                                        </Group>
                                                    </Paper>
                                                ))}
                                            </Stack>
                                        </ScrollArea>
                                    </Stack>
                                </Grid.Col>
                            </Grid>
                        </Stack>
                    ) : (
                        <Stack align="center" justify="center" h="100%" c="dimmed">
                            <IconGavel size={64} style={{ opacity: 0.2 }} />
                            <Text size="xl">{t('neologism_review.court.select_case')}</Text>
                        </Stack>
                    )}
                </Grid.Col>
            </Grid>
        </Box>
    );
};

export default JudgmentCourt;
