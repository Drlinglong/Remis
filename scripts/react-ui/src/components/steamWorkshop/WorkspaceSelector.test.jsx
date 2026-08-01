import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import WorkspaceSelector from './WorkspaceSelector';

describe('WorkspaceSelector', () => {
  it('lets an existing workspace bind or replace its Workshop ID', async () => {
    const onUpdate = vi.fn().mockResolvedValue({
      workspace_id: 'workspace-1',
      workshop_item_id: '3538617386',
    });

    render(
      <MantineProvider>
        <WorkspaceSelector
          error=""
          isSaving={false}
          onCreate={vi.fn()}
          onSelect={vi.fn()}
          onUpdate={onUpdate}
          workspace={{
            workspace_id: 'workspace-1',
            name: 'Remis 发布素材',
            game_id: '281990',
            workshop_item_id: null,
          }}
          workspaces={[{
            workspace_id: 'workspace-1',
            name: 'Remis 发布素材',
          }]}
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: /编辑绑定/ }));
    fireEvent.change(await screen.findByLabelText('Steam Workshop ID（可选）'), {
      target: { value: '3538617386' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith({
        name: 'Remis 发布素材',
        gameId: '281990',
        workshopItemId: '3538617386',
      });
    });
  });
});
