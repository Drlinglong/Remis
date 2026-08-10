import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Paper, Title, Badge, Button, Group } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { TaskCard } from './TaskCard';
import styles from './KanbanColumn.module.css';

const COLUMN_COLORS = {
    todo: 'gray',
    in_progress: 'blue',
    proofreading: 'yellow',
    paused: 'orange',
    done: 'green'
};

export const KanbanColumn = ({ id, tasks, onCardClick, onAddNote }) => {
    const { t } = useTranslation();
    const { setNodeRef } = useDroppable({ id });

    const title = t(`project_management.kanban.columns.${id}`, id);
    const color = COLUMN_COLORS[id] || 'gray';

    return (
        <div className={styles.column}>
            {/* Header */}
            <div className={styles.columnHeader}>
                <Group gap="xs">
                    <Title order={5} style={{ color: 'var(--text-main)' }}>{title}</Title>
                    <Badge color={color} variant="light" size="sm" circle>
                        {tasks.length}
                    </Badge>
                </Group>
                <Button
                    variant="subtle"
                    size="xs"
                    onClick={() => onAddNote(id)}
                    title={t('project_management.kanban.add_note_task')}
                >
                    <IconPlus size={16} />
                </Button>
            </div>

            {/* Task List Area */}
            <div ref={setNodeRef} className={styles.taskList}>
                <SortableContext
                    id={id}
                    items={tasks.map(t => t.id)}
                    strategy={verticalListSortingStrategy}
                >
                    {tasks.map((task) => (
                        <TaskCard
                            key={task.id}
                            task={task}
                            onClick={onCardClick}
                        />
                    ))}
                </SortableContext>

                {/* Empty State / Drop Target hint could go here if needed */}
                {tasks.length === 0 && (
                    <div style={{ height: '50px', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                )}
            </div>
        </div>
    );
};
