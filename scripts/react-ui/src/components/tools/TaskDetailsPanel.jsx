import React, { useState, useEffect } from 'react';
import { Stack, TextInput, Textarea, Select, Button, Text, Group, Badge, Divider } from '@mantine/core';
import { IconDeviceFloppy, IconTrash } from '@tabler/icons-react';
import { useDebouncedCallback } from '@mantine/hooks';
import { useTranslation } from 'react-i18next';

export const TaskDetailsPanel = ({ task, onUpdate, onDelete }) => {
    const { t } = useTranslation();
    const [localComments, setLocalComments] = useState(task.comments || '');
    const [localTitle, setLocalTitle] = useState(task.title || '');

    const STATUS_OPTIONS = [
        { value: 'todo', label: t('project_management.kanban.columns.todo') },
        { value: 'in_progress', label: t('project_management.kanban.columns.in_progress') },
        { value: 'proofreading', label: t('project_management.kanban.columns.proofreading') },
        { value: 'paused', label: t('project_management.kanban.columns.paused') },
        { value: 'done', label: t('project_management.kanban.columns.done') }
    ];

    // Sync local state when task prop changes
    useEffect(() => {
        setLocalComments(task.comments || '');
        setLocalTitle(task.title || '');
    }, [task.comments, task.title, task.id]);

    // Debounce updates to the parent/hook
    const debouncedUpdate = useDebouncedCallback((updates) => {
        onUpdate(task.id, updates);
    }, 500);

    const handleCommentChange = (e) => {
        const val = e.currentTarget.value;
        setLocalComments(val);
        debouncedUpdate({ comments: val });
    };

    const handleTitleChange = (e) => {
        const val = e.currentTarget.value;
        setLocalTitle(val);
        debouncedUpdate({ title: val });
    };

    const handleStatusChange = (val) => {
        onUpdate(task.id, { status: val });
    };

    if (!task) return <Text>{t('project_management.details.no_task_selected')}</Text>;

    return (
        <Stack gap="md" p="xs">
            <Group justify="space-between">
                <Badge
                    color={task.type === 'file' ? 'blue' : 'yellow'}
                    variant="light"
                >
                    {task.type === 'file' ? t('project_management.details.file_task') : t('project_management.details.note_task')}
                </Badge>
                <Text size="xs" c="dimmed">{t('project_management.details.id')}: {task.id}</Text>
            </Group>

            {/* Title */}
            {task.type === 'note' ? (
                <TextInput
                    label={t('project_management.details.title')}
                    value={localTitle}
                    onChange={handleTitleChange}
                />
            ) : (
                <div>
                    <Text size="sm" fw={500} c="dimmed" mb={4}>{t('project_management.details.file_name')}</Text>
                    <Text fw={600} style={{ wordBreak: 'break-all' }}>{task.title}</Text>
                </div>
            )}

            {/* Status */}
            <Select
                label={t('project_management.details.status')}
                data={STATUS_OPTIONS}
                value={task.status || ''}
                onChange={(val) => handleStatusChange(val)}
            />

            {/* File Specific Info */}
            {task.type === 'file' && (
                <Stack gap={4}>
                    <Text size="sm" fw={500} c="dimmed">{t('project_management.details.file_path')}</Text>
                    <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                        {task.filePath}
                    </Text>
                    {task.meta && (
                        <>
                            <Text size="xs" c="dimmed">{t('project_management.details.lines')}: {task.meta.lines}</Text>
                            {task.meta.linked_files && task.meta.linked_files.length > 0 && (
                                <Stack gap={2} mt={4}>
                                    <Text size="xs" fw={500} c="dimmed">Linked Files:</Text>
                                    {task.meta.linked_files.map((lf, i) => (
                                        <Badge key={i} size="xs" variant="outline" color="gray">
                                            {lf}
                                        </Badge>
                                    ))}
                                </Stack>
                            )}
                        </>
                    )}
                </Stack>
            )}

            <Divider my="xs" />

            {/* Comments */}
            <Textarea
                label={t('project_management.details.comments')}
                placeholder={t('project_management.details.placeholder_comments')}
                minRows={4}
                autosize
                value={localComments}
                onChange={handleCommentChange}
            />
            <Text size="xs" c="dimmed" ta="right">
                <IconDeviceFloppy size={12} style={{ marginRight: 4 }} />
                {t('project_management.details.auto_saving')}
            </Text>

            <Divider my="xs" />

            {/* Actions */}
            {task.type === 'note' && (
                <Button
                    color="red"
                    variant="light"
                    leftSection={<IconTrash size={16} />}
                    onClick={() => onDelete(task.id)}
                    fullWidth
                >
                    {t('project_management.details.delete_task')}
                </Button>
            )}
        </Stack>
    );
};
