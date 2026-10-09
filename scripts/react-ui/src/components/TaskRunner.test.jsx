import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { notifications } from '@mantine/notifications';
import api from '../utils/api';
import TaskRunner from './TaskRunner';

vi.mock('../utils/api', () => ({ default: { post: vi.fn() } }));
vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }));
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));
const translate = vi.hoisted(() => (key) => key);
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: translate }) }));

const task = { status: 'completed', log: ['Translation log line'],
  output_dirs: ['J:/output/demo'], result_path: 'J:/output/demo.zip' };
const details = { projectId: 'project-1', gameId: 'victoria3' };
const preview = { preview_id: 'preview-1', source_path: 'J:/output/demo',
  target_path: 'J:/Paradox/mod/demo', target_exists: true, validation_error_count: 0 };
const renderRunner = (overrides = {}) => {
  const props = { task, translationDetails: details, onRestart: vi.fn(), onDashboard: vi.fn(), ...overrides };
  return { ...render(<MantineProvider><TaskRunner {...props} /></MantineProvider>), props };
};

describe('TaskRunner completion actions', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // jsdom does not implement the browser scrolling API used by the log viewport.
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  });
  afterEach(() => { delete HTMLElement.prototype.scrollTo; });

  it.each(['completed', 'partial_failed'])('supports logs, restart and dashboard from %s', async (status) => {
    const { props } = renderRunner({ task: { ...task, status } });
    expect(screen.getByRole('heading', { name: status === 'completed'
      ? 'translation_completed' : 'translation_completed_with_warnings' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'show_detailed_logs' }));
    expect(screen.getByRole('button', { name: 'hide_detailed_logs' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Translation log line')).toBeVisible());
    fireEvent.click(screen.getByRole('button', { name: 'button_translate_another' }));
    fireEvent.click(screen.getByRole('button', { name: 'button_go_dashboard' }));
    expect(props.onRestart).toHaveBeenCalledOnce();
    expect(props.onDashboard).toHaveBeenCalledOnce();
  });

  it.each(['failed', 'cancelled', 'interrupted'])('does not offer output actions for %s', (status) => {
    renderRunner({ task: { ...task, status, message: 'Stopped task' } });
    expect(screen.getByRole('heading', { name: `task_center.status.${status}` })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'button_auto_deploy' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'button_open_folder' })).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('opens the persisted output folder', async () => {
    api.post.mockResolvedValue({ data: {} });
    renderRunner();
    fireEvent.click(screen.getByRole('button', { name: 'button_open_folder' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/system/open_folder', { path: 'J:/output/demo' }));
  });

  it('reports an unavailable output without requesting an arbitrary folder', () => {
    renderRunner({ task: { status: 'completed', log: [] } });
    fireEvent.click(screen.getByRole('button', { name: 'button_open_folder' }));
    expect(api.post).not.toHaveBeenCalled();
    expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
      color: 'red', message: 'error_output_folder_not_available',
    }));
  });

  it('cancels a deployment preview without sending deployment approval', async () => {
    api.post.mockResolvedValue({ data: preview });
    renderRunner();
    fireEvent.click(screen.getByRole('button', { name: 'button_auto_deploy' }));
    const cancel = await screen.findByRole('button', { name: 'cancel' });
    fireEvent.click(cancel);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith('/api/tools/deploy_preview', expect.objectContaining({ project_id: 'project-1' }));
  });

  it('requires overwrite confirmation before sending the approved preview', async () => {
    api.post.mockResolvedValueOnce({ data: preview }).mockResolvedValueOnce({ data: { status: 'success' } });
    renderRunner();
    fireEvent.click(screen.getByRole('button', { name: 'button_auto_deploy' }));
    const deploy = await screen.findByRole('button', { name: 'deploy_btn_direct_deploy' });
    expect(deploy).toBeDisabled();
    fireEvent.click(deploy);
    expect(api.post).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('checkbox', { name: 'deploy_preview_overwrite_confirm' }));
    fireEvent.click(deploy);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/tools/deploy_mod', expect.objectContaining({
      project_id: 'project-1', output_folder_name: 'demo', preview_id: 'preview-1',
      target_deploy_path: preview.target_path, approved: true, confirm_overwrite: true,
    })));
    await waitFor(() => expect(screen.getByRole('button', { name: 'button_auto_deploy' })).toBeDisabled());
  });

  it('keeps deployment retry available after the backend rejects the approved preview', async () => {
    api.post.mockResolvedValueOnce({ data: { ...preview, target_exists: false } })
      .mockResolvedValueOnce({ data: { status: 'error', message: 'Deployment blocked' } });
    renderRunner();
    fireEvent.click(screen.getByRole('button', { name: 'button_auto_deploy' }));
    fireEvent.click(await screen.findByRole('button', { name: 'deploy_btn_direct_deploy' }));
    await waitFor(() => expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
      color: 'red', message: 'Deployment blocked',
    })));
    expect(screen.getByRole('button', { name: 'button_auto_deploy' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'deploy_btn_direct_deploy' })).toBeEnabled();
  });

  it('cancels the second cleanup confirmation and reports a subsequent cleanup failure', async () => {
    api.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith('deploy_info')
      ? { detected_workshop_path: 'J:/Steam/workshop/123', source_language: 'simp_chinese' }
      : { status: 'error', message: 'Cleanup blocked' } }));
    renderRunner();
    fireEvent.click(screen.getByRole('button', { name: 'button_clean_fake_loc' }));
    const clean = await screen.findByRole('button', { name: 'deploy_btn_delete_fake_loc' });
    fireEvent.click(clean);
    const confirm = await screen.findByRole('button', { name: 'deploy_clean_confirm_btn' });
    const confirmationDialog = confirm.closest('[role="dialog"]');
    fireEvent.click(within(confirmationDialog).getByRole('button', { name: 'cancel' }));
    expect(api.post).toHaveBeenCalledTimes(1);
    fireEvent.click(clean);
    fireEvent.click(await screen.findByRole('button', { name: 'deploy_clean_confirm_btn' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/tools/clean_fake_loc', {
      workshop_path: 'J:/Steam/workshop/123', source_language: 'simp_chinese',
    }));
    await waitFor(() => expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
      color: 'red', message: 'Cleanup blocked',
    })));
    expect(screen.getByRole('button', { name: 'button_auto_deploy' })).toBeEnabled();
  });

  it('displays terminal output for Mars without offering Paradox deployment', () => {
    renderRunner({ translationDetails: { ...details, gameId: 'surviving_mars' } });
    expect(screen.getByRole('button', { name: 'button_open_folder' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'button_auto_deploy' })).not.toBeInTheDocument();
  });
});
