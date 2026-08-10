import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import RecentActivityList from './RecentActivityList';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

describe('RecentActivityList', () => {
  it('uses the surface contrast contract for activity details', () => {
    const { container } = render(
      <MantineProvider>
        <RecentActivityList
          activities={[{
            id: 'activity-1',
            title: '蕾姆丝计划 - 演示Mod - 维多利亚3',
            type: 'translate',
            description: 'Translation workflow failed',
            timestamp: '2026-07-22T00:00:00Z',
          }]}
          loading={false}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('蕾姆丝计划 - 演示Mod - 维多利亚3')).toBeInTheDocument();
    expect(screen.getByText(/recent_activity_desc_translate/)).toBeInTheDocument();
    expect(container.querySelector('[data-remis-surface="surface"]')).toBeInTheDocument();
  });

  it('localizes incremental source baseline activity codes', () => {
    render(
      <MantineProvider>
        <RecentActivityList
          activities={[{
            id: 'activity-source-advanced',
            title: 'Demo project',
            type: 'source_advanced',
            description: 'history.incremental_source_advanced_desc',
            timestamp: '2026-07-22T00:00:00Z',
          }]}
          loading={false}
        />
      </MantineProvider>,
    );

    expect(screen.getByText(/recent_activity_desc_source_advanced/)).toBeInTheDocument();
    expect(screen.getByText('recent_activity_type_source_advanced')).toBeInTheDocument();
    expect(screen.queryByText(/history\.incremental_source_advanced_desc/)).not.toBeInTheDocument();
  });

  it('keeps long activity content in normal page flow and caps the visible list', () => {
    const longTitle = 'C:\\Mods\\A-very-long-unbroken-translation-output-path-with-a-stable-id-1234567890';
    const activities = Array.from({ length: 7 }, (_, index) => ({
      id: `activity-${index}`,
      title: index === 0 ? longTitle : `Activity ${index}`,
      type: 'translate',
      description: 'Long activity description',
      timestamp: '2026-07-22T00:00:00Z',
    }));
    const { container } = render(
      <MantineProvider>
        <RecentActivityList activities={activities} loading={false} />
      </MantineProvider>,
    );

    expect(screen.getByText(longTitle)).toBeInTheDocument();
    expect(container.querySelector('[data-remis-activity-list]').querySelectorAll(':scope > .mantine-Group-root')).toHaveLength(5);
    expect(container.querySelector('[data-remis-activity-list] [style*="overflow-y"]')).not.toBeInTheDocument();
  });
});
