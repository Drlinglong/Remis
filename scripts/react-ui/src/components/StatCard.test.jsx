import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it } from 'vitest';

import StatCard from './StatCard';

describe('StatCard', () => {
  it('uses the paper contrast contract for its label and value', () => {
    const { container } = render(
      <MantineProvider>
        <StatCard
          title="项目总数"
          value="13"
          icon={<span>icon</span>}
          color="blue"
          progress={100}
          trend={0}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('项目总数')).toBeInTheDocument();
    expect(screen.getByText('13')).toBeInTheDocument();
    expect(container.querySelector('[data-remis-surface="paper"]')).toBeInTheDocument();
  });
});
