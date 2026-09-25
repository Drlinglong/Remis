import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectFileList from './ProjectFileList';
import api from '../../utils/api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, options) => options?.defaultValue || key }),
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn() },
}));

const projectDetails = (gameId) => ({
  project_id: 'project-1',
  game_id: gameId,
  source_path: 'C:/mods/source',
  translation_dirs: ['C:/mods/output'],
  files: [
    { key: 'source-1', name: 'C:/mods/source/common/file.txt', file_type: 'source', lines: 2, status: 'todo', progress: 0, actions: ['Proofread'] },
    { key: 'translation-1', name: 'C:/mods/output/common/file.txt', file_type: 'translation', lines: 2, status: 'todo', progress: 0, actions: ['Proofread'] },
  ],
});

describe('ProjectFileList structured-game source rows', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(['project_zomboid', 'rimworld'])(
    'keeps %s source rows readable while disabling proofreading writes',
    async (gameId) => {
      api.get.mockResolvedValue({
        data: {
          content: 'source_key = "Original value"',
          file_path: 'J:/mod/reference/common/file.txt',
          read_only: true,
        },
      });
      const handleProofread = vi.fn();
      const onFileStatusChange = vi.fn();

      render(
        <MantineProvider>
          <ProjectFileList
            projectDetails={projectDetails(gameId)}
            handleProofread={handleProofread}
            onFileStatusChange={onFileStatusChange}
          />
        </MantineProvider>,
      );

      const sourceSelect = screen.getAllByRole('textbox')[0];
      expect(sourceSelect).toBeDisabled();
      fireEvent.click(screen.getByRole('button', { name: 'View source' }));
      expect(await screen.findByRole('textbox', { name: 'Source file content' })).toHaveValue('source_key = "Original value"');
      expect(api.get).toHaveBeenCalledWith(
        '/api/projects/project-1/game-resources/source-1/preview',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
      expect(handleProofread).not.toHaveBeenCalled();
      expect(onFileStatusChange).not.toHaveBeenCalled();
      expect(screen.getByText('Source file (read only)')).toBeInTheDocument();
      await waitFor(() => expect(screen.getByLabelText('Source file content')).toHaveAttribute('readonly'));
    },
  );
});
