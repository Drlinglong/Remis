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
  it('uses the paper contrast contract for activity details', () => {
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
    expect(container.querySelector('[data-remis-surface="paper"]')).toBeInTheDocument();
  });
});
