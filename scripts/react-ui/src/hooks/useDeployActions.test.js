import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import { useDeployActions } from './useDeployActions';

vi.mock('../utils/api', () => ({
  default: { post: vi.fn() },
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const wrapper = ({ children }) => React.createElement(MantineProvider, null, children);

const renderDeployActions = (overrides = {}) => {
  const options = {
    getOutputFolderName: () => 'zh-CN-demo',
    projectId: 'project-1',
    gameId: 'victoria3',
    onDeploySuccess: vi.fn(),
    onCleanSuccess: vi.fn(),
    ...overrides,
  };

  return { ...renderHook(() => useDeployActions(options), { wrapper }), options };
};

describe('useDeployActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('deploys only the selected project output to the chosen path', async () => {
    api.post.mockResolvedValue({ data: { status: 'success' } });
    const { result, options } = renderDeployActions();

    act(() => result.current.setDeployPath('J:/Paradox/mod/zh-CN-demo'));
    await act(async () => result.current.handleExecuteDeploy());

    expect(api.post).toHaveBeenCalledWith('/api/tools/deploy_mod', {
      project_id: 'project-1',
      output_folder_name: 'zh-CN-demo',
      game_id: 'victoria3',
      target_deploy_path: 'J:/Paradox/mod/zh-CN-demo',
      clean_fake_loc: false,
      source_language: 'english',
    });
    expect(options.onDeploySuccess).toHaveBeenCalledOnce();
  });

  it('cleans only the detected workshop path and preserves the source language', async () => {
    api.post
      .mockResolvedValueOnce({
        data: {
          default_deploy_path: 'J:/Paradox/mod/zh-CN-demo',
          detected_workshop_path: 'J:/Steam/workshop/123',
          source_language: 'simp_chinese',
        },
      })
      .mockResolvedValueOnce({ data: { status: 'success', removed_files: [], removed_folders: [] } });
    const { result, options } = renderDeployActions();

    act(() => result.current.handleOpenCleanModal());
    await waitFor(() => expect(result.current.infoLoading).toBe(false));
    await act(async () => result.current.handleExecuteClean());

    expect(api.post).toHaveBeenLastCalledWith('/api/tools/clean_fake_loc', {
      workshop_path: 'J:/Steam/workshop/123',
      source_language: 'simp_chinese',
    });
    expect(options.onCleanSuccess).toHaveBeenCalledOnce();
  });

  it('does not report a failed deployment as successful', async () => {
    api.post.mockResolvedValue({ data: { status: 'error', message: 'blocked' } });
    const { result, options } = renderDeployActions();

    await act(async () => result.current.handleExecuteDeploy());

    expect(options.onDeploySuccess).not.toHaveBeenCalled();
    expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
      color: 'red',
      message: 'blocked',
    }));
  });
});
