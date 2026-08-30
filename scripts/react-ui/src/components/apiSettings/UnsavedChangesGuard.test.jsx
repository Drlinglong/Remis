import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React, { useState } from 'react';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, Link, RouterProvider } from 'react-router';
import {
    UnsavedChangesGuardProvider,
    useUnsavedChangesGuard,
} from '../../hooks/useUnsavedChangesGuard';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key) => ({
        settings_unsaved_changes_title: '您还有未保存的改动，确定要现在离开吗？',
        settings_unsaved_changes_message: '您还有未保存的改动，确定要现在离开吗？',
        settings_unsaved_changes_stay: '返回并检查',
        settings_unsaved_changes_discard: '放弃改动并离开',
    }[key] || key) }),
}));

const GuardedSettings = () => {
    const [dirty, setDirty] = useState(true);
    useUnsavedChangesGuard({
        id: 'guard-test',
        isDirty: dirty,
        onDiscard: () => setDirty(false),
    });

    return (
        <div>
            <Link to="/other">离开设置</Link>
            <button type="button" onClick={() => setDirty(false)}>保存</button>
        </div>
    );
};

const renderGuardedSettings = () => {
    const router = createMemoryRouter([
        {
            path: '/settings',
            element: (
                <UnsavedChangesGuardProvider>
                    <GuardedSettings />
                </UnsavedChangesGuardProvider>
            ),
        },
        { path: '/other', element: <div>other page</div> },
    ], { initialEntries: ['/settings'] });

    render(
        <MantineProvider>
            <RouterProvider router={router} />
        </MantineProvider>,
    );
    return router;
};

describe('UnsavedChangesGuard', () => {
    afterEach(() => cleanup());

    it('blocks in-app navigation and discards before proceeding', async () => {
        const router = renderGuardedSettings();

        fireEvent.click(screen.getByRole('link', { name: '离开设置' }));
        expect((await screen.findAllByText('您还有未保存的改动，确定要现在离开吗？')).length).toBe(2);
        fireEvent.click(screen.getByRole('button', { name: '返回并检查' }));
        expect(screen.getByRole('link', { name: '离开设置' })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('link', { name: '离开设置' }));
        fireEvent.click(await screen.findByRole('button', { name: '放弃改动并离开' }));
        await waitFor(() => expect(router.state.location.pathname).toBe('/other'));
        expect(screen.getByText('other page')).toBeInTheDocument();
    });

    it('blocks beforeunload while dirty and clears the guard after saving', async () => {
        renderGuardedSettings();
        const dirtyEvent = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(dirtyEvent);
        expect(dirtyEvent.defaultPrevented).toBe(true);

        fireEvent.click(screen.getByRole('button', { name: '保存' }));
        await waitFor(() => {
            const cleanEvent = new Event('beforeunload', { cancelable: true });
            window.dispatchEvent(cleanEvent);
            expect(cleanEvent.defaultPrevented).toBe(false);
        });
    });
});
