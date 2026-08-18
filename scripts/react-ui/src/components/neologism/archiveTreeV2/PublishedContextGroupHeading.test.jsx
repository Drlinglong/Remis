import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import PublishedContextGroupHeading from './PublishedContextGroupHeading';

const t = (key, options) => options?.defaultValue || key;

const group = {
    id: 'group-1',
    label: 'Opening quest',
    summary: 'The opening event chain.',
};

const renderHeading = (overrides = {}) => render(
    <MantineProvider>
        <PublishedContextGroupHeading
            group={group}
            fragmentCount={2}
            focused
            kicker="EVENT CHAIN"
            onSelectGroup={vi.fn()}
            onRenameGroup={vi.fn()}
            t={t}
            {...overrides}
        />
    </MantineProvider>,
);

const enterRename = () => {
    fireEvent.click(screen.getByRole('button', { name: 'Rename event chain' }));
    return screen.getByRole('textbox', { name: 'Event chain name' });
};

describe('PublishedContextGroupHeading', () => {
    it('exposes the rename entry only for a focused chain and selects the full label on entry', () => {
        const { rerender } = renderHeading({ focused: false });

        expect(screen.queryByRole('button', { name: 'Rename event chain' })).not.toBeInTheDocument();

        rerender(
            <MantineProvider>
                <PublishedContextGroupHeading
                    group={group}
                    fragmentCount={2}
                    focused
                    kicker="EVENT CHAIN"
                    onSelectGroup={vi.fn()}
                    onRenameGroup={vi.fn()}
                    t={t}
                />
            </MantineProvider>,
        );

        const input = enterRename();
        expect(input).toHaveFocus();
        expect(input.selectionStart).toBe(0);
        expect(input.selectionEnd).toBe(group.label.length);
    });

    it('submits a trimmed changed label with Enter and does not submit a second time on blur', () => {
        const onRenameGroup = vi.fn();
        renderHeading({ onRenameGroup });
        const input = enterRename();

        fireEvent.change(input, { target: { value: '  Resolution route  ' } });
        fireEvent.keyDown(input, { key: 'Enter' });
        fireEvent.blur(input);

        expect(onRenameGroup).toHaveBeenCalledTimes(1);
        expect(onRenameGroup).toHaveBeenCalledWith('group-1', 'Resolution route');
        expect(screen.queryByRole('textbox', { name: 'Event chain name' })).not.toBeInTheDocument();
    });

    it('submits a changed label on blur', () => {
        const onRenameGroup = vi.fn();
        renderHeading({ onRenameGroup });
        const input = enterRename();

        fireEvent.change(input, { target: { value: 'Resolution route' } });
        fireEvent.blur(input);

        expect(onRenameGroup).toHaveBeenCalledTimes(1);
        expect(onRenameGroup).toHaveBeenCalledWith('group-1', 'Resolution route');
    });

    it('cancels on Escape and ignores the resulting blur', () => {
        const onRenameGroup = vi.fn();
        renderHeading({ onRenameGroup });
        const input = enterRename();

        fireEvent.change(input, { target: { value: 'Discarded route' } });
        fireEvent.keyDown(input, { key: 'Escape' });
        fireEvent.blur(input);

        expect(onRenameGroup).not.toHaveBeenCalled();
        expect(screen.getByTestId('published-context-group-header-group-1')).toHaveTextContent('Opening quest');
        expect(screen.queryByText('Discarded route')).not.toBeInTheDocument();
    });

    it('rejects blank Enter and blur submissions without leaving the editor or calling the controller', () => {
        const onRenameGroup = vi.fn();
        renderHeading({ onRenameGroup });
        const input = enterRename();

        fireEvent.change(input, { target: { value: '   ' } });
        fireEvent.keyDown(input, { key: 'Enter' });
        fireEvent.blur(input);

        expect(onRenameGroup).not.toHaveBeenCalled();
        expect(screen.getByRole('textbox', { name: 'Event chain name' })).toBeInTheDocument();
    });

    it('does not call the controller when the trimmed label is unchanged', () => {
        const onRenameGroup = vi.fn();
        renderHeading({ onRenameGroup });
        const input = enterRename();

        fireEvent.change(input, { target: { value: '  Opening quest  ' } });
        fireEvent.keyDown(input, { key: 'Enter' });

        expect(onRenameGroup).not.toHaveBeenCalled();
        expect(screen.queryByRole('textbox', { name: 'Event chain name' })).not.toBeInTheDocument();
    });
});
