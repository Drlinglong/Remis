import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { useTranslation } from 'react-i18next';
import { CSS } from '@dnd-kit/utilities';
import { Text, Group, Badge } from '@mantine/core';
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

    let badgeColor = 'gray';
    let badgeLabel = t('project_management.kanban.badge_metadata');
    if (task.type === 'file') {
        if (task.meta?.file_type === 'source') {
            badgeColor = 'blue';
            badgeLabel = t('project_management.kanban.badge_source');
        } else if (task.meta?.file_type === 'translation') {
            badgeColor = 'violet';
            badgeLabel = t('project_management.kanban.badge_translation');
        }
    }
    const badge = <Badge size="xs" color={badgeColor} variant="light">{badgeLabel}</Badge>;

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            aria-label={`${task.title}; ${badgeLabel}`}
            onClick={() => onClick?.(task)}
            onKeyDown={(event) => {
                listeners?.onKeyDown?.(event);
                if (event.key === 'Enter' && !event.defaultPrevented && onClick) {
                    event.preventDefault();
                    onClick(task);
                }
            }}
            data-remis-surface="surface"
            data-task-kind={task.type === 'file' ? 'file' : 'note'}
            className={`${styles.taskCard} ${isDragging ? styles.taskCardDragging : ''} ${task.type === 'file' ? styles.fileTaskIndicator : styles.noteTaskIndicator}`}
        >
            <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Group gap="xs" wrap="nowrap" className={styles.taskIdentity}>
                    {task.type === 'file' ? (
                        <IconFileText size={16} style={{ minWidth: 16 }} color="var(--color-info)" />
                    ) : (
                        <IconNote size={16} style={{ minWidth: 16 }} color="var(--color-warning)" />
                    )}
                    <Text size="sm" fw={600} truncate title={task.title}>
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
