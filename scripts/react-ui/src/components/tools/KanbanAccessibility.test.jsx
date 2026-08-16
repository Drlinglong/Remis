import React from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, fallback) => fallback ?? key }),
}));

const boardSource = readFileSync(
  resolve(process.cwd(), 'src/components/tools/KanbanBoard.jsx'),
  'utf8',
);
const taskCardSource = readFileSync(
  resolve(process.cwd(), 'src/components/tools/TaskCard.jsx'),
  'utf8',
);
const columnStyles = readFileSync(
  resolve(process.cwd(), 'src/components/tools/KanbanColumn.module.css'),
  'utf8',
);

describe('Kanban keyboard and target accessibility', () => {
  it('identifies add-note controls by their destination column', () => {
    const onAddNote = vi.fn();
    render(
      <MantineProvider>
        <KanbanColumn id="todo" tasks={[]} onCardClick={vi.fn()} onAddNote={onAddNote} />
      </MantineProvider>,
    );

    const addNote = screen.getByRole('button', {
      name: 'project_management.kanban.add_note_task — todo',
    });
    expect(addNote).toHaveAttribute(
      'title',
      'project_management.kanban.add_note_task — todo',
    );
    fireEvent.click(addNote);
    expect(onAddNote).toHaveBeenCalledWith('todo');
  });

  it('reserves Enter for details while leaving Space to the drag sensor', () => {
    const onClick = vi.fn();
    render(
      <MantineProvider>
        <TaskCard
          task={{ id: 'note-1', type: 'note', title: 'Verify names', comments: '' }}
          onClick={onClick}
        />
      </MantineProvider>,
    );

    const card = screen.getByRole('button', {
      name: 'Verify names; project_management.kanban.badge_metadata',
    });
    fireEvent.keyDown(card, { key: 'Enter', code: 'Enter' });
    expect(onClick).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(card, { key: ' ', code: 'Space' });
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('configures sortable keyboard coordinates and accessible hit targets', () => {
    expect(boardSource).toContain('KeyboardSensor');
    expect(boardSource).toContain('sortableKeyboardCoordinates');
    expect(boardSource).toContain("start: ['Space']");
    expect(taskCardSource).toContain('listeners?.onKeyDown?.(event)');
    expect(columnStyles).toMatch(/\.addNoteButton\s*\{[\s\S]*min-height: var\(--control-hit-target\)/);
  });
});

