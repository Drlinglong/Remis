import React, { useEffect, useState } from 'react';
import { Stack, Group, Title, ActionIcon, Text, Paper } from '@mantine/core';
import { IconX, IconTrash } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import api from '../../utils/api';
import { useSidebar } from '../../context/SidebarContext';

const ProjectSidebar = ({ projectId, onDeleteNote }) => {
    const { t } = useTranslation();
    const { setSidebarContent } = useSidebar();
    const [history, setHistory] = useState([]);

    const fetchHistory = async () => {
        try {
            const res = await api.get(`/api/project/${projectId}/notes`);
            setHistory(res.data);
        } catch (error) {
            console.error("Failed to load notes history", error);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [projectId]);

    // Expose refresh method if needed, or just auto-refresh on mount
    // For external updates (like adding a note), we might need a trigger or context.
    // For now, let's assume the parent triggers a remount or we use a custom event/context.
    // Actually, passing a 'refreshTrigger' prop might be easiest.

    return (
        <Stack>
            <Group justify="space-between" mb="sm">
                <Title order={5}>{t('project_management.notes_history_title')}</Title>
                <ActionIcon variant="subtle" color="gray" onClick={() => setSidebarContent(null)}>
                    <IconX size={16} />
                </ActionIcon>
            </Group>
            {history.length === 0 ? (
                <Text c="dimmed" fs="italic">No notes recorded yet.</Text>
            ) : (
                history.map((note) => (
                    <Paper key={note.id} withBorder p="sm" radius="md" style={{ background: 'rgba(255,255,255,0.05)' }}>
                        <Group justify="space-between" mb="xs">
                            <Text size="xs" c="dimmed">{new Date(note.created_at).toLocaleString()}</Text>
                            <ActionIcon color="red" variant="subtle" size="xs" onClick={() => onDeleteNote(note.id)}>
                                <IconTrash size={14} />
                            </ActionIcon>
                        </Group>
                        <Text style={{ whiteSpace: 'pre-wrap' }} size="sm">{note.content}</Text>
                    </Paper>
                ))
            )}
        </Stack>
    );
};

export default ProjectSidebar;
