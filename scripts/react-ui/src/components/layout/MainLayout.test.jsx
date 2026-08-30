import React from 'react';
import { render } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { MainLayout } from './MainLayout';

vi.mock('./AppSider', () => ({ AppSider: () => <aside data-testid="app-sider" /> }));
vi.mock('./ContextualSider', () => ({ ContextualSider: () => <aside data-testid="contextual-sider" /> }));
vi.mock('../tasks/TaskCenterDrawer', () => ({ TaskCenterDrawer: () => <div data-testid="task-drawer" /> }));

describe('MainLayout scroll ownership', () => {
  it('marks the center content as the only page scroll owner', () => {
    const { container } = render(
      <MantineProvider>
        <MainLayout><div>content</div></MainLayout>
      </MantineProvider>,
    );

    const owners = container.querySelectorAll('[data-remis-scroll-owner="main-content"]');
    expect(owners).toHaveLength(1);
    expect(owners[0].style.overflowY).toBe('auto');
    expect(container.querySelectorAll('[data-remis-scroll-owner]')).toHaveLength(1);
  });
});
