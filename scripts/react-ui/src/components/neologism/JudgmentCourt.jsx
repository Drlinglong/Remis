import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Grid, Paper, Title, Text, Stack, Group, Button,
    TextInput, ScrollArea, Badge, ActionIcon, LoadingOverlay, Box,
    ThemeIcon, Select, Alert, Checkbox, Modal, SegmentedControl
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
    IconCheck, IconX, IconBulb, IconQuote,
    IconGavel, IconSparkles, IconAlertTriangle, IconBook2, IconExternalLink,
    IconRestore
} from '@tabler/icons-react';
import api from '../../utils/api';
import { normalizeArrayPayload } from '../../utils/payload';

const API_BASE_URL = '/api';

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const settleWithConcurrency = async (items, operation, concurrency = 4) => {
    const results = new Array(items.length);
    let nextIndex = 0;
    const worker = async () => {
        while (nextIndex < items.length) {
            const index = nextIndex;
            nextIndex += 1;
            try {
                results[index] = {
                    status: 'fulfilled',
                    value: await operation(items[index], index),
                };
            } catch (reason) {
                results[index] = { status: 'rejected', reason };
            }
        }
    };
    await Promise.all(
        Array.from(
            { length: Math.min(concurrency, items.length) },
            () => worker(),
        ),
    );
    return results;
};

/**
 * 新词审核法庭组件
 * 负责审核和批准 AI 挖掘的新词候选
 */
const JudgmentCourt = ({
    selectedProject,
    onSelectedProjectChange,
    refreshToken = 0,
    onOpenMining,
    onOpenGlossary
}) => {
    const { t } = useTranslation();
    const [projects, setProjects] = useState([]);
    const [candidates, setCandidates] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [draftSuggestions, setDraftSuggestions] = useState({});
    const [resolution, setResolution] = useState('approve_project');
    const [projectGlossary, setProjectGlossary] = useState(null);
    const [batchSelectedIds, setBatchSelectedIds] = useState([]);
    const [batchConfirmOpen, setBatchConfirmOpen] = useState(null);
    const [batchProcessing, setBatchProcessing] = useState(false);
    const [docketView, setDocketView] = useState('pending');

    useEffect(() => {
        if (selectedId) {
            const candidate = candidates.find(c => c.id === selectedId);
            if (candidate) {
                setResolution((candidate.duplicate_matches || []).length > 0 ? 'duplicate' : 'approve_project');
            }
        }
    }, [selectedId, candidates]);

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            const projectList = normalizeArrayPayload(response.data, ['projects', 'items', 'data', 'results']);
            setProjects(projectList);
            if (!selectedProject && projectList.length > 0) {
                onSelectedProjectChange(projectList[0].project_id);
            }
        } catch (error) {
            console.error("Failed to fetch projects", error);
        }
    }, [onSelectedProjectChange, selectedProject]);

    const fetchCandidates = useCallback(async (projectId, view = 'pending') => {
        setLoading(true);
        try {
            const viewQuery = view === 'pending'
                ? ''
                : `&view=${encodeURIComponent(view)}`;
            const response = await api.get(
                `${API_BASE_URL}/neologisms?project_id=${encodeURIComponent(projectId)}${viewQuery}`,
            );
            const candidateList = normalizeArrayPayload(
                response.data,
                ['candidates', 'neologisms', 'items', 'data', 'results'],
            );
            setCandidates(candidateList);
            setSelectedId(candidateList[0]?.id || null);
            setBatchSelectedIds((current) => current.filter(
                (candidateId) => candidateList.some((candidate) => candidate.id === candidateId),
            ));
        } catch {
            notifications.show({ title: 'Error', message: 'Failed to load candidates', color: 'red' });
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchProjectGlossary = useCallback(async (projectId) => {
        if (!projectId) {
            setProjectGlossary(null);
            return;
        }

        try {
            const response = await api.get(`${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(projectId)}`);
            setProjectGlossary(response.data);
        } catch {
            setProjectGlossary(null);
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
            fetchCandidates(selectedProject, docketView);
            fetchProjectGlossary(selectedProject);
        } else {
            setCandidates([]);
            setProjectGlossary(null);
        }
    }, [docketView, fetchCandidates, fetchProjectGlossary, refreshToken, selectedProject]);

    useEffect(() => {
        setBatchSelectedIds([]);
        setBatchConfirmOpen(null);
    }, [docketView, selectedProject]);

    const handleApprove = async () => {
        if (!selectedId || !selectedProject) return;
        const candidate = candidates.find(c => c.id === selectedId);
        if (!candidate) return;

        setProcessing(true);
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/${selectedId}/approve`, {
                project_id: selectedProject,
                resolution,
                final_translation: editSuggestion,
                glossary_id: projectGlossary?.glossary_id || null,
                source_lang: candidate.source_lang || currentProject?.source_language || 'en',
                target_lang: candidate.target_lang || 'zh-CN'
            });
            const confirmedGlossary = response.data?.glossary || projectGlossary;
            if (response.data?.glossary) {
                setProjectGlossary(response.data.glossary);
            }
            notifications.show({
                title: t(
                    resolution === 'duplicate'
                        ? 'neologism_review.court.duplicate_confirmed_title'
                        : 'neologism_review.court.approved_title'
                ),
                message: t(
                    resolution === 'duplicate'
                        ? 'neologism_review.court.duplicate_confirmed_message'
                        : 'neologism_review.court.approved_message',
                    {
                        term: candidate.original,
                        glossary: confirmedGlossary?.name || t('neologism_review.court.project_glossary'),
                    }
                ),
                color: resolution === 'duplicate' ? 'blue' : 'green',
                icon: <IconCheck size={18} />,
                withBorder: true,
                autoClose: 3200,
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
        const candidate = candidates.find(c => c.id === selectedId);
        if (!candidate) return;
        setProcessing(true);
        try {
            await api.post(`${API_BASE_URL}/neologisms/${selectedId}/reject`, {
                project_id: selectedProject
            });
            notifications.show({
                title: t('neologism_review.court.rejected_title'),
                message: t('neologism_review.court.rejected_message', {
                    term: candidate.original,
                }),
                color: 'gray',
                icon: <IconX size={18} />,
                withBorder: true,
                autoClose: 3200,
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

    const handleRestore = async () => {
        if (!selectedId || !selectedProject) return;
        const candidate = candidates.find(c => c.id === selectedId);
        if (!candidate) return;
        setProcessing(true);
        try {
            const response = await api.post(`${API_BASE_URL}/neologisms/${selectedId}/restore`, {
                project_id: selectedProject,
            });
            notifications.show({
                title: t('neologism_review.court.restored_title'),
                message: t(
                    response.data?.glossary_entry_preserved
                        ? 'neologism_review.court.restored_glossary_preserved'
                        : 'neologism_review.court.restored_message',
                    { term: candidate.original },
                ),
                color: 'blue',
                icon: <IconRestore size={18} />,
                withBorder: true,
                autoClose: 4200,
            });
            removeCandidate(selectedId);
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.restore_failed'),
                color: 'red',
            });
        } finally {
            setProcessing(false);
        }
    };

    const removeCandidates = (ids) => {
        const removedIds = new Set(ids);
        const currentIndex = candidates.findIndex(c => c.id === selectedId);
        const newList = candidates.filter(c => !removedIds.has(c.id));
        setDraftSuggestions((current) => {
            const next = { ...current };
            removedIds.forEach((id) => {
                delete next[`${selectedProject || ''}:${id}`];
            });
            return next;
        });
        setBatchSelectedIds((current) => current.filter((id) => !removedIds.has(id)));
        setCandidates(newList);
        if (selectedId && !removedIds.has(selectedId)) {
            return;
        }
        if (newList.length > 0) {
            const nextIndex = currentIndex >= 0
                ? Math.min(currentIndex, newList.length - 1)
                : 0;
            setSelectedId(newList[nextIndex].id);
        } else {
            setSelectedId(null);
        }
    };

    const removeCandidate = (id) => removeCandidates([id]);

    const toggleBatchCandidate = (candidateId) => {
        setBatchSelectedIds((current) => (
            current.includes(candidateId)
                ? current.filter((id) => id !== candidateId)
                : [...current, candidateId]
        ));
    };

    const toggleAllCandidates = () => {
        setBatchSelectedIds((current) => (
            current.length === candidates.length
                ? []
                : candidates.map((candidate) => candidate.id)
        ));
    };

    const handleBatchReject = async () => {
        if (!selectedProject || batchSelectedIds.length === 0) return;

        const selectedIds = candidates
            .filter((candidate) => batchSelectedIds.includes(candidate.id))
            .map((candidate) => candidate.id);
        if (selectedIds.length === 0) {
            setBatchConfirmOpen(null);
            return;
        }

        setBatchProcessing(true);
        const results = await Promise.allSettled(
            selectedIds.map((candidateId) => api.post(
                `${API_BASE_URL}/neologisms/${candidateId}/reject`,
                { project_id: selectedProject },
            )),
        );
        const succeededIds = [];
        const failedIds = [];
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                succeededIds.push(selectedIds[index]);
            } else {
                failedIds.push(selectedIds[index]);
            }
        });

        if (succeededIds.length > 0) {
            removeCandidates(succeededIds);
        }
        setBatchSelectedIds(failedIds);
        setBatchConfirmOpen(null);
        setBatchProcessing(false);

        if (failedIds.length === 0) {
            notifications.show({
                title: t('neologism_review.court.batch_rejected_title'),
                message: t('neologism_review.court.batch_rejected_message', {
                    count: succeededIds.length,
                }),
                color: 'gray',
                icon: <IconX size={18} />,
                withBorder: true,
                autoClose: 4000,
            });
        } else {
            notifications.show({
                title: t('neologism_review.court.batch_partial_title'),
                message: t('neologism_review.court.batch_partial_message', {
                    succeeded: succeededIds.length,
                    failed: failedIds.length,
                }),
                color: succeededIds.length > 0 ? 'orange' : 'red',
                icon: <IconAlertTriangle size={18} />,
                withBorder: true,
                autoClose: 6000,
            });
        }
    };

    const candidateDraft = (candidate) => {
        const key = `${selectedProject || ''}:${candidate.id}`;
        return Object.prototype.hasOwnProperty.call(draftSuggestions, key)
            ? draftSuggestions[key]
            : candidate.suggestion || '';
    };

    const handleBatchApprove = async () => {
        if (!selectedProject || batchSelectedIds.length === 0) return;
        const selectedCandidates = candidates.filter(
            (candidate) => batchSelectedIds.includes(candidate.id),
        );
        if (selectedCandidates.length === 0) {
            setBatchConfirmOpen(null);
            return;
        }

        setBatchProcessing(true);
        const results = await settleWithConcurrency(selectedCandidates, (candidate) => {
            const duplicate = (candidate.duplicate_matches || []).length > 0;
            const finalTranslation = candidateDraft(candidate).trim();
            if (!duplicate && !finalTranslation) {
                throw new Error('Candidate has no suggested translation');
            }
            return api.post(`${API_BASE_URL}/neologisms/${candidate.id}/approve`, {
                project_id: selectedProject,
                resolution: duplicate ? 'duplicate' : 'approve_project',
                final_translation: finalTranslation,
                glossary_id: projectGlossary?.glossary_id || null,
                source_lang: candidate.source_lang || currentProject?.source_language || 'en',
                target_lang: candidate.target_lang || 'zh-CN',
            });
        });
        const succeededIds = [];
        const failedIds = [];
        results.forEach((result, index) => {
            const candidateId = selectedCandidates[index].id;
            if (result.status === 'fulfilled') {
                succeededIds.push(candidateId);
                if (result.value.data?.glossary) setProjectGlossary(result.value.data.glossary);
            } else {
                failedIds.push(candidateId);
            }
        });

        if (succeededIds.length > 0) removeCandidates(succeededIds);
        setBatchSelectedIds(failedIds);
        setBatchConfirmOpen(null);
        setBatchProcessing(false);
        notifications.show({
            title: t(
                failedIds.length > 0
                    ? 'neologism_review.court.batch_partial_title'
                    : 'neologism_review.court.batch_approved_title',
            ),
            message: t(
                failedIds.length > 0
                    ? 'neologism_review.court.batch_partial_message'
                    : 'neologism_review.court.batch_approved_message',
                { succeeded: succeededIds.length, failed: failedIds.length, count: succeededIds.length },
            ),
            color: failedIds.length > 0 ? (succeededIds.length > 0 ? 'orange' : 'red') : 'green',
            icon: failedIds.length > 0
                ? <IconAlertTriangle size={18} />
                : <IconCheck size={18} />,
            withBorder: true,
            autoClose: failedIds.length > 0 ? 6000 : 4000,
        });
    };

    const handleBatchRestore = async () => {
        if (!selectedProject || batchSelectedIds.length === 0) return;
        const selectedIds = candidates
            .filter((candidate) => batchSelectedIds.includes(candidate.id))
            .map((candidate) => candidate.id);
        setBatchProcessing(true);
        const results = await Promise.allSettled(selectedIds.map(
            (candidateId) => api.post(`${API_BASE_URL}/neologisms/${candidateId}/restore`, {
                project_id: selectedProject,
            }),
        ));
        const succeededIds = [];
        const failedIds = [];
        results.forEach((result, index) => {
            (result.status === 'fulfilled' ? succeededIds : failedIds).push(selectedIds[index]);
        });
        if (succeededIds.length > 0) removeCandidates(succeededIds);
        setBatchSelectedIds(failedIds);
        setBatchConfirmOpen(null);
        setBatchProcessing(false);
        notifications.show({
            title: t(
                failedIds.length > 0
                    ? 'neologism_review.court.batch_partial_title'
                    : 'neologism_review.court.batch_restored_title',
            ),
            message: t(
                failedIds.length > 0
                    ? 'neologism_review.court.batch_partial_message'
                    : 'neologism_review.court.batch_restored_message',
                { succeeded: succeededIds.length, failed: failedIds.length, count: succeededIds.length },
            ),
            color: failedIds.length > 0 ? (succeededIds.length > 0 ? 'orange' : 'red') : 'blue',
            icon: failedIds.length > 0
                ? <IconAlertTriangle size={18} />
                : <IconRestore size={18} />,
            withBorder: true,
            autoClose: failedIds.length > 0 ? 6000 : 4000,
        });
    };

    const selectedCandidate = candidates.find(c => c.id === selectedId);
    const currentProject = projects.find(p => p.project_id === selectedProject);
    const selectedDraftKey = selectedCandidate
        ? `${selectedProject || ''}:${selectedCandidate.id}`
        : null;
    const editSuggestion = selectedCandidate
        ? (Object.prototype.hasOwnProperty.call(draftSuggestions, selectedDraftKey)
            ? draftSuggestions[selectedDraftKey]
            : selectedCandidate.suggestion || "")
        : "";
    const selectedEvidence = selectedCandidate
        ? (
            (selectedCandidate.context_evidence || []).length > 0
                ? selectedCandidate.context_evidence
                : (selectedCandidate.context_snippets || []).map((snippet) => ({
                    snippet,
                    source_file: null,
                    legacy: true,
                }))
        )
        : [];
    const selectedSourceFile = selectedCandidate
        ? (selectedCandidate.source_file || selectedCandidate.source_files?.[0] || '')
        : '';
    const selectedSourceName = selectedSourceFile.split(/[\\/]/).pop()
        || t('neologism_review.court.unknown_source');
    const updateEditSuggestion = (value) => {
        if (!selectedDraftKey) return;
        setDraftSuggestions((current) => ({
            ...current,
            [selectedDraftKey]: value
        }));
    };

    const handleOpenProjectGlossary = () => {
        if (!projectGlossary?.glossary_id || !onOpenGlossary) return;
        onOpenGlossary({
            glossaryId: projectGlossary.glossary_id,
            gameId: projectGlossary.game_id || currentProject?.game_id,
        });
    };

    const HighlightedText = ({ text, term }) => {
        if (!text || !term) return <Text>{text}</Text>;
        const parts = text.split(new RegExp(`(${escapeRegExp(term)})`, 'gi'));
        return (
            <Text size="sm" c="dimmed" lh={1.6} style={{ minWidth: 0 }}>
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
        <Box h="100%" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Modal
                opened={batchConfirmOpen === 'reject'}
                onClose={() => {
                    if (!batchProcessing) setBatchConfirmOpen(null);
                }}
                title={t('neologism_review.court.batch_reject_confirm_title')}
                centered
                closeOnClickOutside={!batchProcessing}
                closeOnEscape={!batchProcessing}
                withCloseButton={!batchProcessing}
            >
                <Stack>
                    <Text>
                        {t('neologism_review.court.batch_reject_confirm_message', {
                            count: batchSelectedIds.length,
                        })}
                    </Text>
                    <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />}>
                        {t('neologism_review.court.batch_reject_confirm_note')}
                    </Alert>
                    <Group justify="flex-end">
                        <Button
                            variant="default"
                            onClick={() => setBatchConfirmOpen(null)}
                            disabled={batchProcessing}
                        >
                            {t('neologism_review.court.batch_cancel')}
                        </Button>
                        <Button
                            color="red"
                            leftSection={<IconX size={18} />}
                            onClick={handleBatchReject}
                            loading={batchProcessing}
                        >
                            {t('neologism_review.court.batch_reject_confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
            <Modal
                opened={batchConfirmOpen === 'approve'}
                onClose={() => {
                    if (!batchProcessing) setBatchConfirmOpen(null);
                }}
                title={t('neologism_review.court.batch_approve_confirm_title')}
                centered
                closeOnClickOutside={!batchProcessing}
                closeOnEscape={!batchProcessing}
                withCloseButton={!batchProcessing}
            >
                <Stack>
                    <Text>
                        {t('neologism_review.court.batch_approve_confirm_message', {
                            count: batchSelectedIds.length,
                        })}
                    </Text>
                    <Alert color="blue" variant="light" icon={<IconAlertTriangle size={18} />}>
                        {t('neologism_review.court.batch_approve_confirm_note')}
                    </Alert>
                    <Group justify="flex-end">
                        <Button
                            variant="default"
                            onClick={() => setBatchConfirmOpen(null)}
                            disabled={batchProcessing}
                        >
                            {t('neologism_review.court.batch_cancel')}
                        </Button>
                        <Button
                            color="green"
                            leftSection={<IconCheck size={18} />}
                            onClick={handleBatchApprove}
                            loading={batchProcessing}
                        >
                            {t('neologism_review.court.batch_approve_confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
            <Modal
                opened={batchConfirmOpen === 'restore'}
                onClose={() => {
                    if (!batchProcessing) setBatchConfirmOpen(null);
                }}
                title={t('neologism_review.court.batch_restore_confirm_title')}
                centered
                closeOnClickOutside={!batchProcessing}
                closeOnEscape={!batchProcessing}
                withCloseButton={!batchProcessing}
            >
                <Stack>
                    <Text>
                        {t('neologism_review.court.batch_restore_confirm_message', {
                            count: batchSelectedIds.length,
                        })}
                    </Text>
                    <Alert color="blue" variant="light" icon={<IconRestore size={18} />}>
                        {t('neologism_review.court.batch_restore_confirm_note')}
                    </Alert>
                    <Group justify="flex-end">
                        <Button
                            variant="default"
                            onClick={() => setBatchConfirmOpen(null)}
                            disabled={batchProcessing}
                        >
                            {t('neologism_review.court.batch_cancel')}
                        </Button>
                        <Button
                            color="blue"
                            leftSection={<IconRestore size={18} />}
                            onClick={handleBatchRestore}
                            loading={batchProcessing}
                        >
                            {t('neologism_review.court.batch_restore_confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
            {/* Project Context Header */}
            <Paper
                p="sm"
                mb="xs"
                mx="md"
                radius="md"
                withBorder
                data-testid="neologism-project-toolbar"
                style={{
                    background: 'var(--glass-bg)',
                    flexShrink: 0
                }}
            >
                <Group justify="space-between" gap="sm" wrap="wrap">
                    <Group gap="xs" style={{ flex: '1 1 420px', minWidth: 0 }}>
                        <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>
                            {t('neologism_review.court.current_project')}
                        </Text>
                        <Select
                            aria-label={t('neologism_review.court.current_project')}
                            data={projects.map(p => ({ value: p.project_id, label: p.name }))}
                            value={selectedProject}
                            onChange={onSelectedProjectChange}
                            placeholder={t('neologism_review.court.select_project')}
                            size="sm"
                            style={{ flex: '1 1 220px', maxWidth: 360 }}
                        />
                        {currentProject && (
                            <Badge size="md" variant="light" color="blue">
                                {t(
                                    docketView === 'pending'
                                        ? 'neologism_review.court.pending_terms'
                                        : 'neologism_review.court.processed_terms',
                                    { count: candidates.length },
                                )}
                            </Badge>
                        )}
                    </Group>
                    <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                        <ThemeIcon color="teal" variant="light" size="md">
                            <IconBook2 size={16} />
                        </ThemeIcon>
                        <Box style={{ minWidth: 0, maxWidth: 220 }}>
                            <Text size="xs" tt="uppercase" fw={700} c="teal">
                                {t('neologism_review.court.project_glossary')}
                            </Text>
                            <Text size="sm" fw={700} truncate>
                                {projectGlossary?.name || t('neologism_review.court.project_glossary_pending')}
                            </Text>
                        </Box>
                        <Button
                            variant="light"
                            color="teal"
                            size="compact-sm"
                            leftSection={<IconExternalLink size={14} />}
                            onClick={handleOpenProjectGlossary}
                            disabled={!projectGlossary?.glossary_id || !onOpenGlossary}
                        >
                            {t('neologism_review.court.inspect_project_glossary')}
                        </Button>
                    </Group>
                </Group>
            </Paper>

            <Grid
                gutter={0}
                style={{ flex: '1 1 0', minHeight: 0, overflow: 'hidden' }}
                styles={{ inner: { height: '100%', minHeight: 0 } }}
            >
                {/* Sidebar List */}
                <Grid.Col
                    span={3}
                    h="100%"
                    style={{
                        borderRight: '1px solid var(--glass-border)',
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 0,
                        overflow: 'hidden'
                    }}
                >
                    <Stack p="sm" gap="xs" h="100%" style={{ minHeight: 0 }}>
                        <Group justify="space-between">
                            <Title order={4} c="dimmed">{t('neologism_review.court.docket')}</Title>
                            <Badge variant="dot" size="lg">{candidates.length}</Badge>
                        </Group>
                        <SegmentedControl
                            fullWidth
                            size="xs"
                            value={docketView}
                            onChange={setDocketView}
                            data={[
                                {
                                    value: 'pending',
                                    label: t('neologism_review.court.pending_docket'),
                                },
                                {
                                    value: 'processed',
                                    label: t('neologism_review.court.processed_docket'),
                                },
                            ]}
                        />
                        {candidates.length > 0 && (
                            <Stack gap="xs">
                                <Checkbox
                                    size="xs"
                                    label={t('neologism_review.court.select_all')}
                                    checked={batchSelectedIds.length === candidates.length}
                                    indeterminate={
                                        batchSelectedIds.length > 0
                                        && batchSelectedIds.length < candidates.length
                                    }
                                    onChange={toggleAllCandidates}
                                    disabled={processing || batchProcessing}
                                />
                                {batchSelectedIds.length > 0 && (
                                    <Group grow gap="xs">
                                        {docketView === 'pending' ? (
                                            <>
                                                <Button
                                                    size="compact-xs"
                                                    variant="light"
                                                    color="green"
                                                    onClick={() => setBatchConfirmOpen('approve')}
                                                    disabled={processing || batchProcessing}
                                                >
                                                    {t('neologism_review.court.batch_approve', {
                                                        count: batchSelectedIds.length,
                                                    })}
                                                </Button>
                                                <Button
                                                    size="compact-xs"
                                                    variant="light"
                                                    color="red"
                                                    onClick={() => setBatchConfirmOpen('reject')}
                                                    disabled={processing || batchProcessing}
                                                >
                                                    {t('neologism_review.court.batch_reject', {
                                                        count: batchSelectedIds.length,
                                                    })}
                                                </Button>
                                            </>
                                        ) : (
                                            <Button
                                                size="compact-xs"
                                                variant="light"
                                                color="blue"
                                                onClick={() => setBatchConfirmOpen('restore')}
                                                disabled={processing || batchProcessing}
                                            >
                                                {t('neologism_review.court.batch_restore', {
                                                    count: batchSelectedIds.length,
                                                })}
                                            </Button>
                                        )}
                                    </Group>
                                )}
                            </Stack>
                        )}
                        <ScrollArea
                            type="always"
                            scrollbars="y"
                            scrollbarSize={8}
                            style={{ flex: 1, minHeight: 0, margin: '0 -8px' }}
                            p="xs"
                        >
                            <Stack gap="xs">
                                {candidates.map(c => (
                                    <Group key={c.id} gap="xs" wrap="nowrap" align="center">
                                        <Checkbox
                                            size="xs"
                                            checked={batchSelectedIds.includes(c.id)}
                                            onChange={() => toggleBatchCandidate(c.id)}
                                            aria-label={t('neologism_review.court.select_candidate', {
                                                term: c.original,
                                            })}
                                            disabled={processing || batchProcessing}
                                        />
                                        <Paper
                                            component="button"
                                            type="button"
                                            p="sm"
                                            radius="sm"
                                            onClick={() => setSelectedId(c.id)}
                                            aria-pressed={selectedId === c.id}
                                            style={{
                                                cursor: 'pointer',
                                                width: '100%',
                                                minWidth: 0,
                                                textAlign: 'left',
                                                color: 'inherit',
                                                font: 'inherit',
                                                backgroundColor: selectedId === c.id ? 'var(--mantine-color-blue-light)' : 'var(--glass-bg)',
                                                border: selectedId === c.id ? '1px solid var(--mantine-color-blue-filled)' : '1px solid transparent',
                                                transition: 'all 0.2s ease'
                                            }}
                                        >
                                            <Text size="sm" fw={600} lineClamp={1}>{c.original}</Text>
                                            {(c.duplicate_matches || []).length > 0 && (
                                                <Badge color="orange" variant="light" size="xs">
                                                    {t('neologism_review.court.duplicate_badge')}
                                                </Badge>
                                            )}
                                            {docketView === 'processed' && (
                                                <Badge color="blue" variant="light" size="xs">
                                                    {t(`neologism_review.court.status_${c.status}`)}
                                                </Badge>
                                            )}
                                            <Text size="xs" c="dimmed" truncate>{c.suggestion}</Text>
                                        </Paper>
                                    </Group>
                                ))}
                                {candidates.length === 0 && !loading && (
                                    <Stack align="center" mt="xl" c="dimmed">
                                        <IconCheck size={32} />
                                        <Text>
                                            {t(
                                                docketView === 'pending'
                                                    ? 'neologism_review.court.caught_up'
                                                    : 'neologism_review.court.no_processed_cases',
                                            )}
                                        </Text>
                                    </Stack>
                                )}
                            </Stack>
                        </ScrollArea>
                    </Stack>
                </Grid.Col>

                {/* Main Review Area */}
                <Grid.Col
                    span={9}
                    h="100%"
                    style={{ position: 'relative', minHeight: 0, overflow: 'hidden' }}
                >
                    {selectedCandidate ? (
                        <Stack
                            h="100%"
                            p="md"
                            gap="sm"
                            data-testid="neologism-review-workspace"
                            style={{ minHeight: 0 }}
                        >
                            <LoadingOverlay visible={processing} />

                            <ScrollArea
                                type="always"
                                scrollbars="y"
                                scrollbarSize={8}
                                style={{ flex: 1, minHeight: 0 }}
                            >
                                <Stack gap="md" pr="xs">
                                    {/* Header Section */}
                                    <Paper
                                        p="md"
                                        radius="md"
                                        style={{
                                            background: 'var(--glass-bg)',
                                            backdropFilter: 'blur(10px)'
                                        }}
                                    >
                                        <Group align="flex-start" justify="space-between">
                                            <Box>
                                                <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>{t('neologism_review.court.candidate_term')}</Text>
                                                <Title order={2} style={{ fontSize: '1.75rem', color: 'var(--mantine-color-blue-3)' }}>
                                                    {selectedCandidate.original}
                                                </Title>
                                            </Box>
                                            <Badge
                                                size="md"
                                                variant="outline"
                                                color="gray"
                                                title={selectedSourceFile || selectedSourceName}
                                                style={{ maxWidth: '45%', minWidth: 0 }}
                                            >
                                                {selectedSourceName}
                                            </Badge>
                                        </Group>
                                    </Paper>

                                    <Grid gutter="md">
                                        {/* Left Column: Analysis */}
                                        <Grid.Col span={7}>
                                            <Stack gap="sm">
                                            {(selectedCandidate.duplicate_matches || []).length > 0 && (
                                                <Alert
                                                    icon={<IconAlertTriangle size={18} />}
                                                    color="orange"
                                                    variant="light"
                                                    title={t('neologism_review.court.duplicate_warning_title')}
                                                >
                                                    <Stack gap={4}>
                                                        <Text size="sm">
                                                            {t('neologism_review.court.duplicate_warning_body')}
                                                        </Text>
                                                        {(selectedCandidate.duplicate_matches || []).slice(0, 3).map((match) => (
                                                            <Text key={match.entry_id || match.source_term} size="xs" c="dimmed">
                                                                {match.source_term} - {match.glossary_name}
                                                            </Text>
                                                        ))}
                                                    </Stack>
                                                </Alert>
                                            )}
                                            <Paper p="md" radius="md" style={{ background: 'rgba(0,0,0,0.2)' }} withBorder>
                                                <Group mb="xs">
                                                    <ThemeIcon color="yellow" variant="light" size="md"><IconBulb size={16} /></ThemeIcon>
                                                    <Text fw={700}>{t('neologism_review.court.ai_analysis')}</Text>
                                                </Group>
                                                <Text size="sm" style={{ lineHeight: 1.6 }}>
                                                    {selectedCandidate.reasoning}
                                                    </Text>
                                                    {selectedCandidate.review_language && (
                                                        <Badge mt="sm" variant="light" color="yellow">
                                                            {t('neologism_review.court.review_language_badge', {
                                                                language: selectedCandidate.review_language,
                                                            })}
                                                        </Badge>
                                                    )}
                                                </Paper>
                                            </Stack>
                                        </Grid.Col>

                                        {/* Right Column: Evidence */}
                                        <Grid.Col span={5} style={{ minWidth: 0 }}>
                                            <Stack style={{ minWidth: 0 }}>
                                                <Text fw={700} c="dimmed" tt="uppercase" size="xs">{t('neologism_review.court.context_evidence')}</Text>
                                                <Stack gap="xs">
                                                    {selectedEvidence.map((evidence, idx) => (
                                                        <Paper
                                                            key={`${evidence.source_file || 'legacy'}:${idx}`}
                                                            p="sm"
                                                            radius="md"
                                                            style={{ background: 'rgba(0,0,0,0.3)', minWidth: 0 }}
                                                        >
                                                            <Stack gap="xs" style={{ minWidth: 0 }}>
                                                                <Group
                                                                    align="flex-start"
                                                                    gap="xs"
                                                                    wrap="nowrap"
                                                                    style={{ minWidth: 0 }}
                                                                >
                                                                    <IconQuote size={16} style={{ opacity: 0.5, marginTop: 4 }} />
                                                                    <HighlightedText
                                                                        text={evidence.snippet}
                                                                        term={selectedCandidate.original}
                                                                    />
                                                                </Group>
                                                                <Text
                                                                    size="xs"
                                                                    c="dimmed"
                                                                    data-testid="neologism-evidence-source"
                                                                    style={{
                                                                        minWidth: 0,
                                                                        whiteSpace: 'normal',
                                                                        overflowWrap: 'anywhere',
                                                                        wordBreak: 'break-word',
                                                                    }}
                                                                >
                                                                    {evidence.source_file
                                                                        ? `${evidence.source_file}${evidence.line ? `:${evidence.line}` : ''}`
                                                                        : t('neologism_review.court.legacy_source_unlinked')}
                                                                </Text>
                                                            </Stack>
                                                        </Paper>
                                                    ))}
                                                </Stack>
                                            </Stack>
                                        </Grid.Col>
                                    </Grid>
                                </Stack>
                            </ScrollArea>

                            {docketView === 'pending' ? (
                                <Paper
                                    p="sm"
                                    radius="md"
                                    withBorder
                                    data-testid="neologism-decision-panel"
                                    style={{ background: 'var(--glass-bg)', flexShrink: 0 }}
                                >
                                    {(selectedCandidate.duplicate_matches || []).length > 0 && (
                                        <Select
                                            mb="sm"
                                            label={t('neologism_review.court.duplicate_resolution')}
                                            data={[
                                                { value: 'duplicate', label: t('neologism_review.court.resolution_duplicate') },
                                                { value: 'approve_project', label: t('neologism_review.court.resolution_override') },
                                                { value: 'new_meaning', label: t('neologism_review.court.resolution_new_meaning') },
                                            ]}
                                            value={resolution}
                                            onChange={setResolution}
                                        />
                                    )}
                                    <TextInput
                                        label={t('neologism_review.court.final_translation')}
                                        description={t('neologism_review.court.final_translation_desc')}
                                        size="md"
                                        radius="md"
                                        value={editSuggestion}
                                        onChange={(e) => updateEditSuggestion(e.currentTarget.value)}
                                        rightSection={
                                            <ActionIcon variant="subtle" onClick={() => updateEditSuggestion(selectedCandidate.suggestion)}>
                                                <IconSparkles size={18} />
                                            </ActionIcon>
                                        }
                                    />
                                    <Group mt="sm" grow>
                                        <Button
                                            size="md"
                                            variant="default"
                                            color="gray"
                                            leftSection={<IconX />}
                                            onClick={handleReject}
                                            disabled={batchProcessing}
                                        >
                                            {t('neologism_review.court.ignore')}
                                        </Button>
                                        <Button
                                            size="md"
                                            variant="gradient"
                                            gradient={{ from: 'teal', to: 'lime', deg: 105 }}
                                            leftSection={<IconGavel />}
                                            onClick={handleApprove}
                                            disabled={
                                                batchProcessing
                                                || !selectedProject
                                                || (resolution !== 'duplicate' && !editSuggestion.trim())
                                            }
                                        >
                                            {t('neologism_review.court.approve')}
                                        </Button>
                                    </Group>
                                </Paper>
                            ) : (
                                <Paper
                                    p="sm"
                                    radius="md"
                                    withBorder
                                    style={{ background: 'var(--glass-bg)', flexShrink: 0 }}
                                >
                                    <Group justify="space-between" align="center">
                                        <Box>
                                            <Text fw={700}>
                                                {t(`neologism_review.court.status_${selectedCandidate.status}`)}
                                            </Text>
                                            <Text size="sm" c="dimmed">
                                                {t(
                                                    ['approved', 'new_meaning'].includes(selectedCandidate.status)
                                                        ? 'neologism_review.court.restore_preserves_glossary_note'
                                                        : 'neologism_review.court.restore_note',
                                                )}
                                            </Text>
                                        </Box>
                                        <Button
                                            color="blue"
                                            variant="light"
                                            leftSection={<IconRestore size={18} />}
                                            onClick={handleRestore}
                                            disabled={batchProcessing}
                                        >
                                            {t('neologism_review.court.restore_candidate')}
                                        </Button>
                                    </Group>
                                </Paper>
                            )}
                        </Stack>
                    ) : selectedProject && candidates.length === 0 && !loading ? (
                        <Stack align="center" justify="center" h="100%" c="dimmed">
                            <IconCheck size={64} style={{ opacity: 0.35 }} />
                            <Text size="xl">
                                {t(
                                    docketView === 'pending'
                                        ? 'neologism_review.court.caught_up'
                                        : 'neologism_review.court.no_processed_cases',
                                )}
                            </Text>
                            {docketView === 'pending' && onOpenMining && (
                                <Button variant="light" onClick={onOpenMining}>
                                    {t('neologism_review.tab_mining')}
                                </Button>
                            )}
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
