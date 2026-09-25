import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import projectService from '../services/projectService';
import { useProjectGameSupport } from './useProjectGameSupport';

vi.mock('../services/projectService', () => ({
  default: { getGameSupport: vi.fn() },
}));

describe('useProjectGameSupport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('keeps a late report bound to the project that requested it', async () => {
    const pending = {};
    projectService.getGameSupport.mockImplementation((projectId) => new Promise((resolve) => {
      pending[projectId] = resolve;
    }));

    const { result, rerender } = renderHook(
      ({ projectId }) => useProjectGameSupport(projectId, 'rimworld'),
      { initialProps: { projectId: 'project-a' } },
    );
    rerender({ projectId: 'project-b' });

    await act(async () => {
      pending['project-a']({ data: { game_id: 'rimworld', metadata: { project: 'A' } } });
      pending['project-b']({ data: { game_id: 'rimworld', metadata: { project: 'B' } } });
    });

    await waitFor(() => expect(result.current.data?.metadata.project).toBe('B'));
    expect(result.current.error).toBeNull();
  });
});
