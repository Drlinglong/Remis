import React, { useState } from 'react';
import { DndContext, DragOverlay, defaultDropAnimationSideEffects, useSensor, useSensors, PointerSensor, closestCorners } from '@dnd-kit/core';
import { createPortal } from 'react-dom';
import { useSidebar } from '../../context/SidebarContext';
import { useKanban } from '../../hooks/useKanban';
import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';
import { TaskDetailsPanel } from './TaskDetailsPanel';
import styles from '../../pages/ProjectManagement.module.css';

const KanbanBoard = ({ projectId }) => {
    const {
        tasks,
        columns,
        moveTask,
        addNoteTask,
        updateTask,
        deleteTask
    } = useKanban(projectId);

    const { setSidebarContent, setSidebarWidth, setSidebarCollapsed } = useSidebar();
    const [activeId, setActiveId] = useState(null); // For DragOverlay

    // Sensors for drag detection
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 5, // Avoid accidental drags when clicking
            },
        })
    );

    const handleDragStart = (event) => {
        setActiveId(event.active.id);
    };

    const handleDragEnd = (event) => {
        const { active, over } = event;
        setActiveId(null);

        if (!over) return;

        const activeId = active.id;
        const overId = over.id;

        // Find the task objects
        const activeTask = tasks.find(t => t.id === activeId);

        // Determine target column
        // If overId is a container (column name), we are dropping into an empty column or at the end
        // If overId is a task, we need to find its column
        let overColumnId;
        if (columns.includes(overId)) {
            overColumnId = overId;
        } else {
            const overTask = tasks.find(t => t.id === overId);
            overColumnId = overTask?.status;
        }

        if (activeTask && overColumnId && activeTask.status !== overColumnId) {
            moveTask(activeId, overColumnId);
        }
    };

    const handleCardClick = (task) => {
        // Inject content into the right sidebar
        setSidebarContent(
            <TaskDetailsPanel
                task={task}
                onUpdate={updateTask}
                onDelete={deleteTask}
            />
        );
        setSidebarWidth(350);
        setSidebarCollapsed(false); // Expand sidebar
    };

    const handleAddNote = (columnId) => {
        const newTask = addNoteTask(columnId);
        // Optional: auto-open sidebar for the new task
        handleCardClick(newTask);
    };

    const activeTask = activeId ? tasks.find(t => t.id === activeId) : null;

    return (
        <div id="kanban-board" className={styles.boardContainer}>
            <DndContext
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
            >
                {columns.map((colId) => (
                    <KanbanColumn
                        key={colId}
                        id={colId}
                        tasks={tasks.filter(t => t.status === colId)}
                        onCardClick={handleCardClick}
                        onAddNote={handleAddNote}
                    />
                ))}

                {createPortal(
                    <DragOverlay
                        dropAnimation={{
                            sideEffects: defaultDropAnimationSideEffects({
                                styles: {
                                    active: {
                                        opacity: '0.5',
                                    },
                                },
                            }),
                        }}
                    >
                        {activeTask ? <TaskCard task={activeTask} /> : null}
                    </DragOverlay>,
                    document.body
                )}
            </DndContext>
        </div>
    );
};
export default KanbanBoard;
