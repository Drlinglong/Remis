import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CopilotFloatingWidget from './CopilotFloatingWidget';

const mocks = vi.hoisted(() => ({
  nextId: 0,
  threadProps: null,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'zh' },
    t: (_key, fallback) => fallback || _key,
  }),
}));

vi.mock('../../context/CopilotContext', () => ({
  useRemisCopilotContext: () => ({ pageContext: { pageId: 'projects' } }),
}));

vi.mock('./RemisCopilotThread', () => ({
  default: (props) => {
    mocks.threadProps = props;
    return <div data-testid="floating-thread" />;
  },
}));

function renderWidget() {
  return render(
    <MemoryRouter initialEntries={['/projects']}>
      <MantineProvider>
        <CopilotFloatingWidget />
      </MantineProvider>
    </MemoryRouter>,
  );
}

describe('CopilotFloatingWidget session lifecycle', () => {
  beforeEach(() => {
    localStorage.clear();
    mocks.nextId = 0;
    mocks.threadProps = null;
    vi.stubGlobal('crypto', {
      randomUUID: () => `draft-${++mocks.nextId}`,
    });
    localStorage.setItem('remis_copilot_sessions_v1', JSON.stringify({
      version: 1,
      activeSessionId: 'history-1',
      sessions: [{
        id: 'history-1',
        title: '历史会话',
        createdAt: '2026-08-30T00:00:00.000Z',
        updatedAt: '2026-08-30T00:00:00.000Z',
        messages: [{ id: 'old', role: 'user', content: '旧消息' }],
      }],
    }));
  });

  it('opens a fresh draft every time and persists it only after the first user message', () => {
    renderWidget();

    fireEvent.click(screen.getByRole('button', { name: '打开 Remis 小助手' }));
    expect(screen.getByTestId('floating-thread')).toBeInTheDocument();
    expect(mocks.threadProps.initialMessages).toEqual([]);
    const firstDraftId = mocks.threadProps.sessionId;

    act(() => mocks.threadProps.onMessagesChange(firstDraftId, []));
    expect(JSON.parse(localStorage.getItem('remis_copilot_sessions_v1')).sessions).toHaveLength(1);

    act(() => mocks.threadProps.onMessagesChange(firstDraftId, [{
      id: 'new-user', role: 'user', content: '新的问题',
    }]));
    const persisted = JSON.parse(localStorage.getItem('remis_copilot_sessions_v1'));
    expect(persisted.sessions).toHaveLength(2);
    expect(persisted.sessions[0]).toMatchObject({ id: firstDraftId, title: '新的问题' });
    expect(persisted.activeSessionId).toBe('history-1');

    fireEvent.click(screen.getByRole('button', { name: '关闭' }));
    fireEvent.click(screen.getByRole('button', { name: '打开 Remis 小助手' }));
    expect(mocks.threadProps.sessionId).not.toBe(firstDraftId);
    expect(mocks.threadProps.initialMessages).toEqual([]);
  });

  it('does not retain the placeholder session when the first floating draft is saved', () => {
    localStorage.clear();
    renderWidget();

    fireEvent.click(screen.getByRole('button', { name: '打开 Remis 小助手' }));
    const draftId = mocks.threadProps.sessionId;
    act(() => mocks.threadProps.onMessagesChange(draftId, [{
      id: 'first-user', role: 'user', content: '第一次提问',
    }]));

    const persisted = JSON.parse(localStorage.getItem('remis_copilot_sessions_v1'));
    expect(persisted.sessions).toHaveLength(1);
    expect(persisted.sessions[0]).toMatchObject({ id: draftId, title: '第一次提问' });
    expect(persisted.activeSessionId).toBe(draftId);
  });

  it('merges against the latest page state instead of overwriting it with a stale snapshot', () => {
    renderWidget();
    localStorage.setItem('remis_copilot_sessions_v1', JSON.stringify({
      version: 1,
      activeSessionId: 'page-session',
      sessions: [{
        id: 'page-session',
        title: '页面里的对话',
        createdAt: '2026-08-31T04:20:00.000Z',
        updatedAt: '2026-08-31T04:20:00.000Z',
        messages: [{ id: 'page-user', role: 'user', content: '页面消息' }],
      }],
    }));

    fireEvent.click(screen.getByRole('button', { name: '打开 Remis 小助手' }));
    const floatingId = mocks.threadProps.sessionId;
    act(() => mocks.threadProps.onMessagesChange(floatingId, [{
      id: 'floating-user', role: 'user', content: '气泡消息',
    }]));

    const persisted = JSON.parse(localStorage.getItem('remis_copilot_sessions_v1'));
    expect(persisted.sessions.map((session) => session.id)).toEqual([
      floatingId,
      'page-session',
    ]);
    expect(persisted.activeSessionId).toBe('page-session');
  });
});
