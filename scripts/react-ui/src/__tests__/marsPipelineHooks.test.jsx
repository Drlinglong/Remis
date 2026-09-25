import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/marsPipelineService', () => ({
  default: {
    planImport: vi.fn(),
    import: vi.fn(),
    options: vi.fn(),
    publication: vi.fn(),
    bindPublication: vi.fn(),
    planExport: vi.fn(),
    export: vi.fn(),
  },
}));

import service from '../services/marsPipelineService';
import { useMarsPipelineImport } from '../hooks/useMarsPipelineImport';
import { useMarsPipelineDelivery } from '../hooks/useMarsPipelineDelivery';
import { useMarsPublicationIdentity } from '../hooks/useMarsPublicationIdentity';

const deferred = () => {
  let resolve;
  const promise = new Promise((complete) => { resolve = complete; });
  return { promise, resolve };
};

const projectOptions = (projectId) => ({
  data: {
    supported: true,
    project_id: projectId,
    run_id: 'plan-run',
    translation_outputs: [
      { output_folder_name: 'zh-CN-Loc', language_code: 'zh-CN' },
      { output_folder_name: 'fr-FR-Loc', language_code: 'fr-FR' },
    ],
  },
});

describe('useMarsPipelineImport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('discards a pending preview when an import field changes', async () => {
    const request = deferred();
    service.planImport.mockReturnValue(request.promise);
    const { result } = renderHook(() => useMarsPipelineImport(undefined, 'Example Mod'));
    act(() => {
      result.current.update('path', 'ModContent.fpk');
    });

    let pending;
    act(() => { pending = result.current.preview(); });
    await waitFor(() => expect(service.planImport).toHaveBeenCalledOnce());
    act(() => result.current.update('path', 'changed.fpk'));
    await act(async () => {
      request.resolve({ data: { plan_id: 'stale-plan', review_items: [] } });
      await pending;
    });

    expect(result.current.plan).toBeNull();
    expect(result.current.busy).toBe(false);
    await act(async () => result.current.execute());
    expect(service.import).not.toHaveBeenCalled();
  });

  it('sends the selected archive, prior run, and reviewed IDs in the import preview', async () => {
    service.planImport.mockResolvedValue({ data: { plan_id: 'plan-import', review_items: [] } });
    const { result } = renderHook(() => useMarsPipelineImport(undefined, 'Example Mod'));
    act(() => {
      result.current.update('path', 'ModContent.fpk');
      result.current.update('previousRun', 'plan_previous');
    });

    await act(async () => result.current.preview(['reviewed-id']));

    expect(service.planImport).toHaveBeenCalledWith({
      archive_path: 'ModContent.fpk',
      name: 'Example Mod',
      previous_run_id: 'plan_previous',
      approved_ids: ['reviewed-id'],
      delivery_mode: 'source_copy',
    });
    expect(result.current.plan.plan_id).toBe('plan-import');
  });

  it('sends text-only mode and inherited project name when requested', async () => {
    service.planImport.mockResolvedValue({ data: { plan_id: 'text-only-plan', review_items: [] } });
    const { result } = renderHook(() => useMarsPipelineImport(undefined, 'Inherited Mod Name'));
    act(() => {
      result.current.update('path', 'ModContent.fpk');
      result.current.update('deliveryMode', 'text_only');
    });

    await act(async () => result.current.preview());

    expect(service.planImport).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Inherited Mod Name', delivery_mode: 'text_only',
    }));
  });
});

describe('useMarsPipelineDelivery', () => {
  beforeEach(() => vi.clearAllMocks());

  it('aborts the old options request and ignores its result after a project change', async () => {
    const oldRequest = deferred();
    let oldSignal;
    service.options.mockImplementation((projectId, config) => {
      if (projectId === 'project-old') {
        oldSignal = config.signal;
        return oldRequest.promise;
      }
      return Promise.resolve(projectOptions(projectId));
    });
    const { result, rerender } = renderHook(
      ({ projectId }) => useMarsPipelineDelivery(projectId, 'surviving_mars'),
      { initialProps: { projectId: 'project-old' } },
    );
    await waitFor(() => expect(service.options).toHaveBeenCalledWith(
      'project-old', expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));

    rerender({ projectId: 'project-new' });
    await waitFor(() => expect(result.current.options?.project_id).toBe('project-new'));
    expect(oldSignal.aborted).toBe(true);

    await act(async () => {
      oldRequest.resolve(projectOptions('project-old'));
      await oldRequest.promise;
    });
    expect(result.current.options.project_id).toBe('project-new');
  });

  it('previews a complete source copy with each selected language output', async () => {
    service.options.mockImplementation(async (projectId) => projectOptions(projectId));
    service.planExport.mockResolvedValue({ data: {
      plan_id: 'plan-delivery', status: 'ready', allowed_actions: ['approve_delivery'],
    } });
    service.export.mockResolvedValue({ data: { package_path: 'local-output' } });
    const { result } = renderHook(() => useMarsPipelineDelivery('project-1', 'surviving_mars'));
    await waitFor(() => expect(result.current.options?.supported).toBe(true));
    act(() => result.current.update('selected', ['zh-CN-Loc', 'fr-FR-Loc']));

    await act(async () => result.current.preview());

    expect(service.planExport).toHaveBeenCalledWith('project-1', {
      mode: 'source_copy',
      outputs: [
        { output_folder_name: 'zh-CN-Loc', language_code: 'zh-CN' },
        { output_folder_name: 'fr-FR-Loc', language_code: 'fr-FR' },
      ],
    });
    expect(result.current.plan.plan_id).toBe('plan-delivery');

    await act(async () => result.current.execute());
    expect(service.export).toHaveBeenCalledWith('project-1', 'plan-delivery');
  });

  it('supports a text-only translation delivery without exposing overlay mode', async () => {
    service.options.mockImplementation(async (projectId) => projectOptions(projectId));
    service.planExport.mockResolvedValue({ data: { plan_id: 'text-delivery-plan' } });
    const { result } = renderHook(() => useMarsPipelineDelivery('project-1', 'surviving_mars'));
    await waitFor(() => expect(result.current.options?.supported).toBe(true));
    act(() => {
      result.current.update('mode', 'text_only');
      result.current.update('selected', ['zh-CN-Loc']);
    });

    await act(async () => result.current.preview());

    expect(service.planExport).toHaveBeenCalledWith('project-1', {
      mode: 'text_only', outputs: [{ output_folder_name: 'zh-CN-Loc', language_code: 'zh-CN' }],
    });
  });

  it('invalidates a delivery plan when a field changes', async () => {
    service.options.mockImplementation(async (projectId) => projectOptions(projectId));
    service.planExport.mockResolvedValue({ data: { plan_id: 'stale-plan' } });
    const { result } = renderHook(() => useMarsPipelineDelivery('project-1', 'surviving_mars'));
    await waitFor(() => expect(result.current.options?.supported).toBe(true));
    act(() => result.current.update('selected', ['zh-CN-Loc']));
    await act(async () => result.current.preview());
    expect(result.current.plan.plan_id).toBe('stale-plan');

    act(() => result.current.update('mode', 'text_only'));
    await act(async () => result.current.execute());

    expect(result.current.plan).toBeNull();
    expect(service.export).not.toHaveBeenCalled();
  });

  it('clears a cached export plan and reloads options after publication binding changes', async () => {
    service.options.mockImplementation(async (projectId) => projectOptions(projectId));
    service.planExport.mockResolvedValue({ data: { plan_id: 'stale-plan' } });
    const { result } = renderHook(() => useMarsPipelineDelivery('project-1', 'surviving_mars'));
    await waitFor(() => expect(result.current.options?.supported).toBe(true));
    act(() => result.current.update('selected', ['zh-CN-Loc']));
    await act(async () => result.current.preview());
    expect(result.current.plan.plan_id).toBe('stale-plan');

    act(() => result.current.publicationChanged());
    await waitFor(() => expect(service.options).toHaveBeenCalledTimes(2));
    expect(result.current.plan).toBeNull();
    expect(result.current.result).toBeNull();
    await act(async () => result.current.execute());
    expect(service.export).not.toHaveBeenCalled();
  });
});

describe('useMarsPublicationIdentity', () => {
  beforeEach(() => vi.clearAllMocks());

  it('binds the supplied item using the current unbound revision contract', async () => {
    service.publication.mockResolvedValue({ data: { status: 'unbound', revision: 0 } });
    service.bindPublication.mockResolvedValue({ data: {
      status: 'bound', revision: 1, steam_id: '3807689989', url: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3807689989',
    } });
    const { result } = renderHook(() => useMarsPublicationIdentity('project-1'));
    await waitFor(() => expect(result.current.identity?.status).toBe('unbound'));
    act(() => result.current.updateSteamId('3807689989'));
    let saved;
    await act(async () => { saved = await result.current.bind(); });
    expect(saved).toBe(true);
    expect(service.bindPublication).toHaveBeenCalledWith('project-1', {
      approved: true, expected_revision: 0, steam_id: '3807689989',
    });
    expect(result.current.identity.revision).toBe(1);
  });

  it('refuses to change an already bound ID from this screen', async () => {
    service.publication.mockResolvedValue({ data: { status: 'bound', revision: 4, steam_id: '100' } });
    const { result } = renderHook(() => useMarsPublicationIdentity('project-1'));
    await waitFor(() => expect(result.current.identity?.revision).toBe(4));
    act(() => result.current.updateSteamId('200'));
    let saved;
    await act(async () => { saved = await result.current.bind(); });
    expect(saved).toBe(false);
    expect(service.bindPublication).not.toHaveBeenCalled();
  });

  it('ignores a late binding response after switching projects', async () => {
    const pending = deferred();
    service.publication.mockImplementation(async (projectId) => ({ data: {
      status: 'bound', revision: 1, steam_id: projectId === 'project-old' ? '100' : '200',
    } }));
    service.bindPublication.mockReturnValue(pending.promise);
    const { result, rerender } = renderHook(({ projectId }) => useMarsPublicationIdentity(projectId), {
      initialProps: { projectId: 'project-old' },
    });
    await waitFor(() => expect(result.current.identity?.steam_id).toBe('100'));
    act(() => result.current.updateSteamId('300'));
    let pendingBind;
    act(() => { pendingBind = result.current.bind(); });
    rerender({ projectId: 'project-new' });
    await waitFor(() => expect(result.current.identity?.steam_id).toBe('200'));
    await act(async () => { pending.resolve({ data: { status: 'bound', revision: 2, steam_id: '300' } }); await pendingBind; });
    expect(result.current.identity.steam_id).toBe('200');
  });

  it('surfaces a binding error without changing the saved identity', async () => {
    service.publication.mockResolvedValue({ data: { status: 'unbound', revision: 0 } });
    service.bindPublication.mockRejectedValue(new Error('conflict'));
    const { result } = renderHook(() => useMarsPublicationIdentity('project-1'));
    await waitFor(() => expect(result.current.identity?.status).toBe('unbound'));
    act(() => result.current.updateSteamId('3807689989'));
    await act(async () => result.current.bind());
    expect(result.current.identity.status).toBe('unbound');
    expect(result.current.error).toBe('conflict');
  });

  it('does not bind when publication state failed to load', async () => {
    service.publication.mockRejectedValue(new Error('offline'));
    const { result } = renderHook(() => useMarsPublicationIdentity('project-1'));
    await waitFor(() => expect(result.current.error).toBe('offline'));
    act(() => result.current.updateSteamId('3807689989'));
    let saved;
    await act(async () => { saved = await result.current.bind(); });
    expect(saved).toBe(false);
    expect(service.bindPublication).not.toHaveBeenCalled();
  });
});
