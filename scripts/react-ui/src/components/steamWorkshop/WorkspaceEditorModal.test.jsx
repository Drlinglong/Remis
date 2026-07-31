import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import WorkspaceEditorModal from './WorkspaceEditorModal';

describe('WorkspaceEditorModal', () => {
  it('binds a new publishing workspace to an existing Remis project', async () => {
    const onSave = vi.fn().mockResolvedValue({ workspace_id: 'workspace-1' });
    render(
      <MantineProvider>
        <WorkspaceEditorModal
          isSaving={false}
          opened
          onClose={vi.fn()}
          onSave={onSave}
          projects={[{ project_id: 'project-1', name: '演示项目' }]}
        />
      </MantineProvider>,
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog.closest('[data-remis-surface="elevated"]')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-header')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-title')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-body')).toBeInTheDocument();
    expect(dialog.querySelector('.mantine-Modal-close')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: /工作区名称/ }), {
      target: { value: '演示发布素材' },
    });
    fireEvent.click(screen.getByRole('textbox', { name: '绑定 Remis 项目（可选）' }));
    fireEvent.click(await screen.findByText('演示项目'));
    fireEvent.click(screen.getByRole('button', { name: '创建工作区' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        name: '演示发布素材',
        projectId: 'project-1',
      }));
    });
  });
});
