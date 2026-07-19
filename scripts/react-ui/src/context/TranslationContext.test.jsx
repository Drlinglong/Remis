import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TranslationProvider } from './TranslationContext';
import { useTranslationContext } from './TranslationContextCore';

const { apiGetMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(() => Promise.resolve({ data: { status: 'processing' } })),
}));

vi.mock('../utils/api', () => ({
  default: { get: apiGetMock },
}));

class MockWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.close = vi.fn();
    MockWebSocket.instances.push(this);
  }
}

const ContextSnapshot = () => {
  const context = useTranslationContext();
  return (
    <dl>
      <dt>task</dt><dd>{context.taskId ?? 'none'}</dd>
      <dt>project</dt><dd>{context.selectedProjectId ?? 'none'}</dd>
      <dt>details</dt><dd>{context.translationDetails?.modName ?? 'none'}</dd>
      <dt>processing</dt><dd>{String(context.isProcessing)}</dd>
      <dt>step</dt><dd>{context.activeStep}</dd>
      <dt>status</dt><dd>{context.taskStatus?.status ?? 'none'}</dd>
    </dl>
  );
};

const renderProvider = () => render(
  <TranslationProvider>
    <ContextSnapshot />
  </TranslationProvider>,
);

describe('TranslationProvider workflow handoff', () => {
  beforeEach(() => {
    sessionStorage.clear();
    apiGetMock.mockClear();
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('restores Copilot task handoff state after a page reload', () => {
    sessionStorage.setItem('trans_task_id', JSON.stringify('task-42'));
    sessionStorage.setItem('trans_selected_project_id', JSON.stringify('project-7'));
    sessionStorage.setItem('trans_translation_details', JSON.stringify({
      modName: 'Reloaded Mod',
      sourceLang: 'en',
      targetLangs: ['zh-CN'],
    }));
    sessionStorage.setItem('trans_is_processing', JSON.stringify(false));

    renderProvider();

    expect(screen.getByText('task-42')).toBeInTheDocument();
    expect(screen.getByText('project-7')).toBeInTheDocument();
    expect(screen.getByText('Reloaded Mod')).toBeInTheDocument();
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('persists terminal WebSocket status into the workflow completion state', async () => {
    sessionStorage.setItem('trans_task_id', JSON.stringify('task-live'));
    sessionStorage.setItem('trans_is_processing', JSON.stringify(true));
    sessionStorage.setItem('trans_active_step', JSON.stringify(1));

    renderProvider();

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(MockWebSocket.instances[0].url).toContain('/api/ws/status/task-live');

    act(() => {
      MockWebSocket.instances[0].onmessage({
        data: JSON.stringify({ status: 'partial_failed', completed_files: 8, failed_files: 1 }),
      });
    });

    expect(screen.getByText('partial_failed')).toBeInTheDocument();
    expect(screen.getByText('false')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(sessionStorage.getItem('trans_is_processing')).toBe('false');
    expect(sessionStorage.getItem('trans_active_step')).toBe('3');
  });
});
