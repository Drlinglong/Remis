import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import WorkspaceEditorModal from './WorkspaceEditorModal';

// Regression: ISSUE-003 — free-text game IDs allowed inconsistent workspace data
// Found by /qa on 2026-08-01
// Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-08-01.md
describe('WorkspaceEditorModal supported game selection', () => {
  it('saves the canonical ID selected from the supported game list', async () => {
    const onSave = vi.fn().mockResolvedValue({ workspace_id: 'workspace-1' });
    render(
      <MantineProvider>
        <WorkspaceEditorModal
          games={[
            { value: 'victoria3', label: 'Victoria 3' },
            { value: 'stellaris', label: 'Stellaris' },
          ]}
          isSaving={false}
          opened
          onClose={vi.fn()}
          onSave={onSave}
        />
      </MantineProvider>,
    );

    fireEvent.change(screen.getByRole('textbox', { name: /工作区名称/ }), {
      target: { value: 'Vic3 发布素材' },
    });
    fireEvent.click(screen.getByRole('textbox', { name: '游戏（可选）' }));
    fireEvent.click(await screen.findByText('Victoria 3'));
    fireEvent.click(screen.getByRole('button', { name: '创建工作区' }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      gameId: 'victoria3',
    })));
  });
});
