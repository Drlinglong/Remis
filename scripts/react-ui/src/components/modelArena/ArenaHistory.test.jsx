import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArenaHistory from './ArenaHistory';

describe('ArenaHistory project retention', () => {
  it('marks a retained run when its original project no longer exists', () => {
    render(
      <MantineProvider>
        <ArenaHistory
          t={(key) => key}
          runs={[{
            run_id: 'run-retained',
            project_id: 'deleted-project',
            project_name_snapshot: 'Deleted demo',
            status: 'completed',
            source_lang_code: 'en',
            target_lang_code: 'zh-CN',
            sample_size: 6,
            sample_seed: 'seed-1',
          }]}
          projects={[{ project_id: 'active-project', name: 'Active demo' }]}
          loading={false}
          onOpen={vi.fn()}
          onPreviewExport={vi.fn()}
          onDelete={vi.fn()}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('Deleted demo')).toBeInTheDocument();
    expect(screen.getByText('model_arena.project_deleted')).toBeInTheDocument();
  });
});
