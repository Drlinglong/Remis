import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import { useNeologismMiningTaskMonitor } from './useNeologismMiningTaskMonitor';

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
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

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

const renderMonitor = (callbacks = {}, projectId = 'project-1') => {
  const props = {
    onStatus: vi.fn(),
    onTerminal: vi.fn(),
    onWebSocketError: vi.fn(),
    ...callbacks,
  };
  const hook = renderHook(
    ({ currentProjectId }) => useNeologismMiningTaskMonitor({
      projectId: currentProjectId,
      ...props,
    }),
    { initialProps: { currentProjectId: projectId } },
  );
  return { ...hook, props };
};

describe('useNeologismMiningTaskMonitor', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
    global.WebSocket = FakeWebSocket;
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('polls a silent websocket until the mining task reaches terminal status', async () => {
    api.get
      .mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1', total_files: 2 } })
      .mockResolvedValueOnce({ data: { status: 'completed', task_id: 'task-1', processed_files: 2 } });

    const { props, unmount } = renderMonitor();
    await act(async () => flushPromises());

    expect(FakeWebSocket.instances).toHaveLength(1);
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await flushPromises();
    });

    expect(props.onStatus).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'completed', processed_files: 2 }),
      'polling',
    );
    expect(props.onTerminal).toHaveBeenCalledOnce();
    expect(api.get).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await flushPromises();
    });
    expect(api.get).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('refreshes the server status when the page becomes visible', async () => {
    api.get
      .mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1' } })
      .mockResolvedValueOnce({ data: { status: 'failed', task_id: 'task-1', error: 'provider failed' } });

    const { props, unmount } = renderMonitor();
    await act(async () => flushPromises());

    document.dispatchEvent(new Event('visibilitychange'));
    await act(async () => flushPromises());

    expect(api.get).toHaveBeenCalledTimes(2);
    expect(props.onTerminal).toHaveBeenCalledOnce();
    expect(props.onStatus).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'failed', error: 'provider failed' }),
      'polling',
    );
    unmount();
  });

  it('keeps polling after a malformed websocket message', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.get
      .mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1' } })
      .mockResolvedValueOnce({ data: { status: 'completed', task_id: 'task-1' } });

    const { props, unmount } = renderMonitor();
    await act(async () => flushPromises());

    const socket = FakeWebSocket.instances[0];
    expect(() => socket.onmessage({ data: '{bad json' })).not.toThrow();
    expect(props.onWebSocketError).toHaveBeenCalledOnce();
    expect(errorSpy).toHaveBeenCalledWith(
      'Failed to parse neologism mining WebSocket message',
      expect.any(SyntaxError),
    );

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await flushPromises();
    });
    expect(props.onTerminal).toHaveBeenCalledOnce();
    unmount();
  });

  it('reconnects after a websocket disconnect while the polling fallback stays active', async () => {
    api.get
      .mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1' } })
      .mockResolvedValueOnce({ data: { status: 'completed', task_id: 'task-1' } });

    const { props, unmount } = renderMonitor();
    await act(async () => flushPromises());
    const firstSocket = FakeWebSocket.instances[0];

    act(() => firstSocket.onclose());
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await flushPromises();
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(props.onTerminal).toHaveBeenCalledOnce();
    unmount();
  });

  it('invokes the terminal callback once when websocket terminal events race', async () => {
    api.get.mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1' } });

    const { props, unmount } = renderMonitor();
    await act(async () => flushPromises());
    const socket = FakeWebSocket.instances[0];
    const handleMessage = socket.onmessage;
    const terminalMessage = { data: JSON.stringify({ status: 'completed', task_id: 'task-1' }) };

    act(() => {
      handleMessage(terminalMessage);
      handleMessage(terminalMessage);
    });

    expect(props.onTerminal).toHaveBeenCalledOnce();
    unmount();
  });

  it('cleans the socket, polling, and visibility listener on project switch and unmount', async () => {
    api.get
      .mockResolvedValueOnce({ data: { status: 'running', task_id: 'task-1' } })
      .mockResolvedValueOnce({ data: { status: 'idle' } });
    const removeListenerSpy = vi.spyOn(document, 'removeEventListener');

    const { rerender, unmount } = renderMonitor();
    await act(async () => flushPromises());
    const socket = FakeWebSocket.instances[0];

    rerender({ currentProjectId: 'project-2' });
    await act(async () => flushPromises());
    expect(socket.close).toHaveBeenCalledOnce();
    expect(removeListenerSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await flushPromises();
    });
    expect(api.get).toHaveBeenCalledTimes(2);
    unmount();
  });
});
