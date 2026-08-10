import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { useTranslation } from 'react-i18next';
import { CSS } from '@dnd-kit/utilities';
import { Paper, Text, Group, Badge, ActionIcon, Tooltip } from '@mantine/core';
import { IconFileText, IconNote } from '@tabler/icons-react';
import styles from './TaskCard.module.css';

export const TaskCard = ({ task, onClick }) => {
    const { t } = useTranslation();
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: task.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    // Determine badge content
    let badge = null;
    if (task.type === 'file') {
        if (task.meta?.file_type === 'source') {
            badge = <Badge size="xs" color="blue" variant="light">{t('project_management.kanban.badge_source')}</Badge>;
        } else if (task.meta?.file_type === 'translation') {
            badge = <Badge size="xs" color="violet" variant="light">{t('project_management.kanban.badge_translation')}</Badge>;
        } else if (task.meta?.file_type === 'metadata' || task.meta?.file_type === 'config') {
            badge = <Badge size="xs" color="gray" variant="light">{t('project_management.kanban.badge_metadata')}</Badge>;
        }
    } else {
        // Assume note or other types are metadata related or just generic
        badge = <Badge size="xs" color="gray" variant="light">{t('project_management.kanban.badge_metadata')}</Badge>;
    }

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            onClick={() => onClick(task)}
            className={`${styles.taskCard} ${isDragging ? styles.taskCardDragging : ''} ${task.type === 'file' ? styles.fileTaskIndicator : styles.noteTaskIndicator}`}
        >
            <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Group gap="xs" wrap="nowrap" style={{ flex: 1, overflow: 'hidden' }}>
                    {task.type === 'file' ? (
                        <IconFileText size={16} style={{ minWidth: 16 }} color="var(--color-info)" />
                    ) : (
                        <IconNote size={16} style={{ minWidth: 16 }} color="var(--color-warning)" />
                    )}
                    <Text size="sm" fw={500} truncate title={task.title}>
                        {task.title}
                    </Text>
                </Group>
                {badge}
            </Group>

            {task.type === 'file' && task.meta && (
                <Text size="xs" c="dimmed" mt={4}>
                    {t('project_management.details.lines_count', { count: task.meta.source_lines || task.meta.lines })}
                </Text>
            )}

            {task.comments && (
                <Text size="xs" c="dimmed" lineClamp={2} mt={4} style={{ fontStyle: 'italic' }}>
                    {task.comments}
                </Text>
            )}
        </div>
    );
};
