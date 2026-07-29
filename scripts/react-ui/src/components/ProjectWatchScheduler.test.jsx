import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProjectWatchScheduler from './ProjectWatchScheduler';
import projectWatchService from '../services/projectWatchService';

vi.mock('../services/projectWatchService', () => ({
  default: {
    scanDueWatches: vi.fn(),
  },
}));

describe('ProjectWatchScheduler', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectWatchService.scanDueWatches.mockResolvedValue({ data: [] });
  });

  it('checks for an overdue scan immediately when Remis opens', async () => {
    render(<ProjectWatchScheduler />);

    await waitFor(() => {
      expect(projectWatchService.scanDueWatches).toHaveBeenCalledTimes(1);
    });
  });
});
