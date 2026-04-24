import React from 'react';
import { AppShell, Box } from '@mantine/core';
import { AppSider } from './AppSider';
import { ContextualSider } from './ContextualSider';

export function MainLayout({ children }) {
    return (
        <AppShell
            padding={0}
            style={{ height: '100vh', overflow: 'hidden' }}
        >
            <AppShell.Main style={{ padding: 0, height: '100vh', display: 'flex', overflow: 'hidden', background: 'transparent' }}>
                <Box style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
                    {/* Left Sidebar (Navigation) */}
                    <AppSider />

                    {/* Center Content */}
                    <Box style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0, overflow: 'hidden' }}>
                        <Box style={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: 'auto', overflowX: 'hidden', scrollbarGutter: 'stable' }}>
                            {children}
                        </Box>
                    </Box>

                    {/* Right Sidebar (Context) */}
                    <ContextualSider />
                </Box>
            </AppShell.Main>
        </AppShell>
    );
}
