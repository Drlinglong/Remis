import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Container, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle, IconArchive } from '@tabler/icons-react';

import ContextTreeV2ArchiveSummary from './archiveTreeV2/ContextTreeV2ArchiveSummary';
import { contextResearchPreviewToArchiveTree } from './archiveTreeV2/contextResearchPreviewAdapter';
import styles from './ModArchive.module.css';

const PREVIEW_URL = '/__remis/context-research-preview.json';

const useResearchArtifact = () => {
    const [state, setState] = useState({ phase: 'loading', artifact: null, error: null });
    useEffect(() => {
        let cancelled = false;
        fetch(PREVIEW_URL)
            .then((response) => {
                if (!response.ok) throw new Error(`research_preview_http_${response.status}`);
                return response.json();
            })
            .then((artifact) => {
                if (!cancelled) setState({ phase: 'ready', artifact, error: null });
            })
            .catch((error) => {
                if (!cancelled) setState({ phase: 'error', artifact: null, error: error.message });
            });
        return () => { cancelled = true; };
    }, []);
    return state;
};

const ResearchArtifactStatus = ({ artifact }) => {
    const draft = artifact?.draft || {};
    const release = artifact?.release || {};
    return (
        <Alert
            color="yellow"
            icon={<IconAlertTriangle size={18} />}
            data-testid="context-research-read-only-warning"
        >
            <Stack gap={4}>
                <Text fw={700}>Horizon Signal 研究结果 · 只读预览</Text>
                <Text size="sm">
                    该结果的 published 状态为 {String(release.published ?? false)}，不会写入项目档案或触发发布。
                    覆盖 {draft.source_item_ids?.length || 0} 个源条目、{draft.event_chains?.length || 0} 个事件步骤、
                    {draft.entities?.length || 0} 个实体。
                </Text>
                <Text size="xs" className={styles.technical}>
                    release: {release.release_id || '—'}
                </Text>
            </Stack>
        </Alert>
    );
};

export default function ResearchArtifactPreviewPanel({ projectToolbar }) {
    const { phase, artifact, error } = useResearchArtifact();
    const tree = useMemo(
        () => (artifact ? contextResearchPreviewToArchiveTree(artifact) : null),
        [artifact],
    );
    return (
        <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
            {projectToolbar}
            {phase === 'loading' && (
                <Paper className={`${styles.surface} ${styles.stateCard}`} p="xl" withBorder data-testid="context-research-preview-loading">
                    <Group justify="center"><Loader size="md" /><Text>正在加载 Horizon r2 只读结果…</Text></Group>
                </Paper>
            )}
            {phase === 'error' && (
                <Paper className={`${styles.surface} ${styles.stateCard}`} p="xl" withBorder data-testid="context-research-preview-error">
                    <Stack align="center" gap="sm">
                        <IconArchive size={30} />
                        <Title order={3}>无法加载研究结果</Title>
                        <Text className={styles.muted}>{error}</Text>
                    </Stack>
                </Paper>
            )}
            {phase === 'ready' && artifact && tree && (
                <Stack gap="md">
                    <ResearchArtifactStatus artifact={artifact} />
                    <ContextTreeV2ArchiveSummary tree={tree} mode="preview" />
                </Stack>
            )}
        </Container>
    );
}
