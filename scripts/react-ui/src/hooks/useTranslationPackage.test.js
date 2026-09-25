import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationPackageService from '../services/translationPackageService';
import { useTranslationPackage } from './useTranslationPackage';

vi.mock('../services/translationPackageService', () => ({
  default: {
    getOptions: vi.fn(),
    createPlan: vi.fn(),
    createPackage: vi.fn(),
  },
}));

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const options = (name) => ({
  data: {
    supported: true,
    source_mod: { id: name, title: name },
    translation_outputs: [
      { output_folder_name: `${name}-out`, path: `/${name}/out`, language_code: 'zh-CN' },
      { output_folder_name: `${name}-other`, path: `/${name}/other`, language_code: 'ar-SA' },
    ],
    languages: [{ code: 'zh-CN', name: 'Chinese', game_language: 'Chinese' }],
  },
});

describe('useTranslationPackage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('ignores options responses from a previous project', async () => {
    const oldOptions = deferred();
    const newOptions = deferred();
    translationPackageService.getOptions.mockImplementation((projectId) => (
      projectId === 'old-project' ? oldOptions.promise : newOptions.promise
    ));
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationPackage(projectId, 'surviving_mars'),
      { initialProps: { projectId: 'old-project' } },
    );

    rerender({ projectId: 'new-project' });
    await act(async () => oldOptions.resolve(options('old')));
    await act(async () => newOptions.resolve(options('new')));

    await waitFor(() => expect(result.current.options?.source_mod.id).toBe('new'));
    expect(result.current.outputFolderName).toBe('new-out');
    expect(result.current.targetLanguage).toBe('zh-CN');
  });

  it('invalidates a plan response when the selected output changes', async () => {
    translationPackageService.getOptions.mockResolvedValue(options('mars'));
    const pendingPlan = deferred();
    translationPackageService.createPlan.mockReturnValue(pendingPlan.promise);
    const { result } = renderHook(() => useTranslationPackage('mars-project', 'surviving_mars'));

    await waitFor(() => expect(result.current.options).not.toBeNull());
    act(() => { void result.current.createPlan(); });
    act(() => result.current.updateField('outputFolderName', 'mars-other'));
    await act(async () => pendingPlan.resolve({ data: { plan_id: 'stale-plan', requires_approval: true } }));

    expect(result.current.outputFolderName).toBe('mars-other');
    expect(result.current.targetLanguage).toBe('ar-SA');
    expect(result.current.plan).toBeNull();
    expect(result.current.planning).toBe(false);
  });

  it('ignores plan responses if the owning project changes before they complete', async () => {
    translationPackageService.getOptions.mockImplementation((projectId) => Promise.resolve(options(projectId)));
    const pendingPlan = deferred();
    translationPackageService.createPlan.mockReturnValue(pendingPlan.promise);
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationPackage(projectId, 'surviving_mars'),
      { initialProps: { projectId: 'first' } },
    );

    await waitFor(() => expect(result.current.options).not.toBeNull());
    act(() => { void result.current.createPlan(); });
    rerender({ projectId: 'second' });
    await act(async () => pendingPlan.resolve({ data: { plan_id: 'first-project-plan', requires_approval: true } }));

    await waitFor(() => expect(result.current.options?.source_mod.id).toBe('second'));
    expect(result.current.plan).toBeNull();
  });

  it('does not show a generated result from the previous project', async () => {
    translationPackageService.getOptions.mockImplementation((projectId) => Promise.resolve(options(projectId)));
    translationPackageService.createPlan.mockResolvedValue({
      data: { plan_id: 'plan-first', requires_approval: true },
    });
    const pendingPackage = deferred();
    translationPackageService.createPackage.mockReturnValue(pendingPackage.promise);
    const { result, rerender } = renderHook(
      ({ projectId }) => useTranslationPackage(projectId, 'surviving_mars'),
      { initialProps: { projectId: 'first' } },
    );

    await waitFor(() => expect(result.current.options).not.toBeNull());
    await act(async () => result.current.createPlan());
    await waitFor(() => expect(result.current.plan?.plan_id).toBe('plan-first'));
    act(() => { void result.current.generatePackage(); });
    rerender({ projectId: 'second' });
    await act(async () => pendingPackage.resolve({ data: { package_path: '/first/package' } }));

    await waitFor(() => expect(result.current.options?.source_mod.id).toBe('second'));
    expect(result.current.result).toBeNull();
  });
});
