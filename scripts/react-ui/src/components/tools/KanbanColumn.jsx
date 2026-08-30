import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Title, Badge, Button, Group, Text } from '@mantine/core';
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
    const addNoteLabel = `${t('project_management.kanban.add_note_task')} — ${title}`;

    return (
        <section className={styles.column} data-remis-surface="surface" aria-labelledby={`kanban-column-${id}`}>
            <div className={styles.columnHeader}>
                <Group gap="xs">
                    <Title id={`kanban-column-${id}`} order={5} className={styles.columnTitle}>{title}</Title>
                    <Badge color={color} variant="light" size="sm" circle>
                        {tasks.length}
                    </Badge>
                </Group>
                <Button
                    variant="subtle"
                    size="xs"
                    className={styles.addNoteButton}
                    onClick={() => onAddNote(id)}
                    aria-label={addNoteLabel}
                    title={addNoteLabel}
                >
                    <IconPlus size={16} aria-hidden="true" />
                </Button>
            </div>

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

                {tasks.length === 0 && (
                    <div className={styles.emptyColumn}>
                        <Text size="xs">{t('project_management.kanban.empty_column', 'Drop a task here')}</Text>
                    </div>
                )}
            </div>
        </section>
    );
};
