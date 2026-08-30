import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import HomeDashboardView from './HomeDashboardView';

const retryMock = vi.fn();
const t = (key, options) => options?.defaultValue || key;

vi.mock('../../components/ProjectStatusPieChart', () => ({
  default: ({ data }) => <div data-testid="status-chart">{data.length}</div>,
}));

vi.mock('../../components/ProjectDistributionPieChart', () => ({
  default: ({ data }) => <div data-testid="distribution-chart">{data.length}</div>,
}));

vi.mock('../../components/RecentActivityList', () => ({
  default: ({ error, loading }) => <div data-testid="recent-activity" data-error={error} data-loading={loading} />,
}));

vi.mock('../../components/StatCard', () => ({
  default: ({ title, value }) => <div data-testid="stat-card">{title}:{value}</div>,
}));

vi.mock('./HomeLiveWorkSection', () => ({
  default: () => <section data-remis-anchor="live-work" data-testid="live-work" />,
}));

const dashboardData = {
  stats: { total_projects: null, active_projects: null, completion_rate: null },
  charts: { project_status: [], project_distribution: [] },
  recentActivity: [],
};

const renderView = (phase = 'ready', error = null) => render(
  <MantineProvider>
    <HomeDashboardView
      dashboard={{ data: dashboardData, error, phase, refresh: retryMock }}
      greeting="早上好"
      liveWork={{}}
      t={t}
    />
  </MantineProvider>,
);

describe('HomeDashboardView', () => {
  it('keeps dashboard failure scoped and does not replace missing values with zeros', () => {
    renderView('error', new Error('dashboard offline'));

    expect(screen.getByText('dashboard offline')).toBeInTheDocument();
    expect(screen.getByTestId('live-work')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toHaveAttribute(
      'data-remis-action',
      'paper-secondary',
    );
    expect(screen.getAllByTestId('stat-card').every((card) => card.textContent.endsWith('—'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retryMock).toHaveBeenCalledTimes(1);
  });

  it('keeps the Live Work anchor singular while loading dashboard regions independently', () => {
    renderView('loading');

    expect(screen.getAllByTestId('live-work')).toHaveLength(1);
    expect(screen.getByTestId('recent-activity')).toHaveAttribute('data-loading', 'true');
    expect(screen.getAllByLabelText('home-chart-loading')).toHaveLength(2);
  });
});
