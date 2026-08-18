import React from 'react';
import { DndContext } from '@dnd-kit/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import PublishedContextMiniRail from './PublishedContextMiniRail';

const renderRail = (onSelectGroup = vi.fn()) => {
    const group = {
        id: 'group-2',
        label: 'A very long event chain title',
    };

    render(
        <MantineProvider>
            <DndContext>
                <PublishedContextMiniRail
                    group={group}
                    fragmentCount={3}
                    onSelectGroup={onSelectGroup}
                />
            </DndContext>
        </MantineProvider>,
    );

    return { group, onSelectGroup };
};

describe('PublishedContextMiniRail', () => {
    it('exposes a group droppable target and count badge', () => {
        const { group } = renderRail();
        const rail = screen.getByTestId('published-context-mini-rail-group-2');

        expect(rail).toHaveAttribute('data-drop-target', 'group:group-2');
        expect(rail).toHaveAttribute('data-drag-over', 'false');
        expect(rail).toHaveAttribute('title', group.label);
        expect(rail).toHaveTextContent(group.label);
        expect(rail).toHaveTextContent('3');
    });

    it('switches the focused chain when the rail is clicked', () => {
        const onSelectGroup = vi.fn();
        renderRail(onSelectGroup);

        fireEvent.click(screen.getByTestId('published-context-mini-rail-group-2'));

        expect(onSelectGroup).toHaveBeenCalledWith('group-2');
    });
});
