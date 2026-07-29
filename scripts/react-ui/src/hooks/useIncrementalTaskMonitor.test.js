import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useIncrementalTaskMonitor } from './useIncrementalTaskMonitor';

vi.mock('../services/projectService', () => ({
  default: {
    getTaskStatus: vi.fn(),
  },
}));

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.close = vi.fn();
    FakeWebSocket.instances.push(this);
  }
}

const renderMonitor = (overrides = {}) => {
  const defaults = {
    addLog: vi.fn(),
    executionInFlightRef: { current: false },
    preScanInFlightRef: { current: false },
    setActive: vi.fn(),
    setConflictingTaskId: vi.fn(),
    setCurrentTaskId: vi.fn(),
    setCurrentTaskMode: vi.fn(),
    setExecuting: vi.fn(),
    setFinalSummary: vi.fn(),
    setLoading: vi.fn(),
    setLogs: vi.fn(),
    setProgress: vi.fn(),
    setProgressInfo: vi.fn(),
    setScanResults: vi.fn(),
    t: (key) => key,
  };

  const props = { ...defaults, ...overrides };
  const hook = renderHook(() => useIncrementalTaskMonitor(props));
  return { ...hook, props };
};

describe('useIncrementalTaskMonitor', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    global.WebSocket = FakeWebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('does not append a websocket error after a task already completed', () => {
    const { props, result } = renderMonitor();

    act(() => {
      result.current.connectWebSocket('task-1', false);
    });

    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.onmessage({
        data: JSON.stringify({
          status: 'completed',
          progress: { percent: 100 },
        }),
      });
      socket.onerror(new Error('late close error'));
    });

    expect(props.addLog).toHaveBeenCalledTimes(1);
    expect(props.addLog).toHaveBeenCalledWith('incremental_translation.translation_completed_success');
    expect(props.setConflictingTaskId).toHaveBeenCalledWith(null);
  });

  it('logs websocket errors while a task is still active', () => {
    const { props, result } = renderMonitor();

    act(() => {
      result.current.connectWebSocket('task-1', true);
    });

    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.onerror(new Error('network error'));
    });

    expect(props.addLog).toHaveBeenCalledWith('incremental_translation.status_ws_error');
  });

  it('keeps polling alive when a websocket message is malformed', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { props, result } = renderMonitor();

    act(() => {
      result.current.connectWebSocket('task-1', true);
    });

    const socket = FakeWebSocket.instances[0];
    act(() => {
      expect(() => socket.onmessage({ data: '{bad json' })).not.toThrow();
    });

    expect(props.addLog).toHaveBeenCalledWith('incremental_translation.status_ws_error');
    expect(errorSpy).toHaveBeenCalledWith('Failed to parse incremental task WebSocket message:', expect.any(SyntaxError));
  });
});
