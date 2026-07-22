import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useProjectManagementData } from './useProjectManagementData';
import configService from '../services/configService';
import projectService from '../services/projectService';

vi.mock('../services/configService', () => ({
  default: {
    getConfig: vi.fn(),
  },
}));

vi.mock('../services/projectService', () => ({
  default: {
    checkArchive: vi.fn(),
    getProjectConfig: vi.fn(),
    getProjectFiles: vi.fn(),
    getProjectValidationStatus: vi.fn(),
    getProjectsByStatus: vi.fn(),
  },
}));

describe('useProjectManagementData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();

    configService.getConfig.mockResolvedValue({
      data: {
        game_profiles: {},
        languages: {},
      },
    });
    projectService.getProjectsByStatus.mockResolvedValue({
      data: { projects: [{ project_id: 'project-1', name: 'Project 1', status: 'active' }] },
    });
    projectService.getProjectConfig.mockResolvedValue({
      data: {
        source_language: 'en',
        source_path: 'C:/mods/project-1',
        translation_dirs: ['C:/mods/project-1/localization'],
      },
    });
    projectService.getProjectFiles.mockResolvedValue({
      data: { files: [{ file_id: 'file-1', file_path: 'loc/a.yml', line_count: 20, status: 'done' }] },
    });
    projectService.checkArchive.mockResolvedValue({
      data: {
        exists: true,
        archived_languages: ['zh-CN'],
        source_entry_count: 20,
      },
    });
    projectService.getProjectValidationStatus.mockResolvedValue({
      data: { issues_count: 2, last_updated_at: '2026-07-22T00:00:00Z' },
    });
  });

  it('normalizes wrapped project list payloads', async () => {
    const { result } = renderHook(() => useProjectManagementData());

    await waitFor(() => {
      expect(result.current.projects).toEqual([
        { project_id: 'project-1', name: 'Project 1', status: 'active' },
      ]);
    });
  });

  it('normalizes wrapped project file payloads before building details', async () => {
    const { result } = renderHook(() => useProjectManagementData());

    await waitFor(() => {
      expect(result.current.projects).toHaveLength(1);
    });

    act(() => {
      result.current.setSelectedProjectId('project-1');
    });

    await waitFor(() => {
      expect(result.current.projectDetails).toMatchObject({
        project_id: 'project-1',
        validation: { issues_count: 2 },
        overview: {
          totalFiles: 1,
          totalLines: 20,
        },
        files: [
          {
            key: 'file-1',
            name: 'loc/a.yml',
          },
        ],
      });
    });
  });
});
