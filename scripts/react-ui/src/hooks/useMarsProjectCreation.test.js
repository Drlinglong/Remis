import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/marsPipelineService', () => ({ default: {
  inspectInput: vi.fn(), planImport: vi.fn(), import: vi.fn(),
} }));
import service from '../services/marsPipelineService';
import { useMarsProjectCreation } from './useMarsProjectCreation';

const props = () => ({ opened: true, game: 'surviving_mars', path: 'J:/workshop/3816401225',
  name: 'Grom', language: 'en', onCreated: vi.fn(), createEditable: vi.fn() });

describe('Mars folder project creation', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    service.inspectInput.mockResolvedValue({ data: { kind: 'archive', archive_path: 'J:/mod/ModContent.fpk' } });
    service.planImport.mockResolvedValue({ data: { plan_id: 'plan-1', source_blockers: [],
      review_items: [{ id: 'uncertain', text: 'Keep unchanged' }], allowed_actions: ['approve_preparation'] } });
    service.import.mockResolvedValue({ data: { status: 'prepared', project_id: 'mars-1' } });
  });

  it('discovers, prepares and opens the project while leaving uncertain candidates unapproved', async () => {
    const options = props();
    const { result } = renderHook(() => useMarsProjectCreation(options));
    await act(async () => result.current.create());
    expect(service.inspectInput).toHaveBeenCalledWith(options.path);
    expect(service.planImport).toHaveBeenCalledWith({ archive_path: 'J:/mod/ModContent.fpk',
      name: 'Grom', source_language: 'en', source_column: 'Text', delivery_mode: 'source_copy' });
    expect(service.import).toHaveBeenCalledWith('plan-1');
    expect(options.onCreated).toHaveBeenCalledWith('mars-1');
  });

  it('keeps editable CSV folders on the existing import route', async () => {
    service.inspectInput.mockResolvedValue({ data: { kind: 'editable_folder' } });
    const options = props();
    const { result } = renderHook(() => useMarsProjectCreation(options));
    await act(async () => result.current.create());
    expect(options.createEditable).toHaveBeenCalledOnce();
    expect(service.planImport).not.toHaveBeenCalled();
  });

  it('surfaces source blockers without creating or falling back', async () => {
    service.planImport.mockResolvedValue({ data: { source_blockers: [{ message: 'Conflicting originals' }], allowed_actions: [] } });
    const options = props();
    const { result } = renderHook(() => useMarsProjectCreation(options));
    await act(async () => result.current.create());
    expect(result.current.error).toBe('Conflicting originals');
    expect(service.import).not.toHaveBeenCalled();
    expect(options.createEditable).not.toHaveBeenCalled();
  });

  it('does not call acceptance completion until preparation is persisted as prepared', async () => {
    service.import.mockResolvedValue({ data: { status: 'failed', warnings: ['Import failed'] } });
    const options = props();
    const { result } = renderHook(() => useMarsProjectCreation(options));
    await act(async () => result.current.create());
    expect(options.onCreated).not.toHaveBeenCalled();
    expect(result.current.error).toBe('Import failed');
  });

  it('ignores stale inspection when the user changes the folder and prevents duplicate submissions', async () => {
    let resolve;
    service.inspectInput.mockReturnValue(new Promise((done) => { resolve = done; }));
    const options = props();
    const { result, rerender } = renderHook((input) => useMarsProjectCreation(input), { initialProps: options });
    let pending;
    act(() => { pending = result.current.create(); });
    await act(async () => result.current.create());
    expect(service.inspectInput).toHaveBeenCalledOnce();
    rerender({ ...options, path: 'J:/other' });
    await act(async () => { resolve({ data: { kind: 'archive', archive_path: 'J:/old.fpk' } }); await pending; });
    expect(service.planImport).not.toHaveBeenCalled();
    expect(options.onCreated).not.toHaveBeenCalled();
  });

  it.each([
    ['plan', 'close'], ['plan', 'folder change'], ['plan', 'unmount'],
    ['import', 'close'], ['import', 'folder change'], ['import', 'unmount'],
  ])('ignores a late %s response after %s', async (phase, invalidation) => {
    let resolve;
    const operation = phase === 'plan' ? service.planImport : service.import;
    operation.mockReturnValue(new Promise((done) => { resolve = done; }));
    const options = props();
    const { result, rerender, unmount } = renderHook((input) => useMarsProjectCreation(input), { initialProps: options });
    let pending;
    act(() => { pending = result.current.create(); });
    await waitFor(() => expect(operation).toHaveBeenCalledOnce());
    if (invalidation === 'unmount') unmount();
    else rerender({ ...options, ...(invalidation === 'close' ? { opened: false } : { path: 'J:/other' }) });
    await act(async () => {
      resolve({ data: phase === 'plan'
        ? { plan_id: 'old-plan', source_blockers: [], allowed_actions: ['approve_preparation'] }
        : { status: 'prepared', project_id: 'old-project' } });
      await pending;
    });
    if (phase === 'plan') expect(service.import).not.toHaveBeenCalled();
    expect(options.onCreated).not.toHaveBeenCalled();
    expect(options.createEditable).not.toHaveBeenCalled();
    if (invalidation !== 'unmount') expect(result.current).toMatchObject({ busy: false, error: '', stage: '' });
  });
});
