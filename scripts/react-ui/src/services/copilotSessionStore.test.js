import { beforeEach, describe, expect, it } from 'vitest';
import {
  createEmptySession,
  createSessionInState,
  deleteSessionInState,
  loadCopilotState,
  serializeThreadMessages,
  setActiveSessionInState,
  toInitialMessages,
  upsertSessionMessages,
} from './copilotSessionStore';

describe('copilotSessionStore', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('loads a default empty session when storage is empty', () => {
    const state = loadCopilotState();
    expect(state.sessions).toHaveLength(1);
    expect(state.activeSessionId).toBe(state.sessions[0].id);
  });

  it('persists messages and restores them', () => {
    let state = loadCopilotState();
    const id = state.activeSessionId;
    state = upsertSessionMessages(state, id, [
      { role: 'user', content: '第一次汉化该怎么走？' },
      { role: 'assistant', content: '先创建项目', metadata: { custom: { confidence: 'high' } } },
    ]);
    const reloaded = loadCopilotState();
    const session = reloaded.sessions.find((s) => s.id === id);
    expect(session.messages).toHaveLength(2);
    expect(session.title).toContain('第一次汉化');
    expect(toInitialMessages(session.messages)[1].metadata.custom.confidence).toBe('high');
  });

  it('supports multiple sessions and deletion', () => {
    let state = loadCopilotState();
    const first = state.activeSessionId;
    state = createSessionInState(state);
    expect(state.sessions.length).toBe(2);
    expect(state.activeSessionId).not.toBe(first);
    state = setActiveSessionInState(state, first);
    expect(state.activeSessionId).toBe(first);
    state = deleteSessionInState(state, first);
    expect(state.sessions.some((s) => s.id === first)).toBe(false);
  });

  it('serializes thread-like messages', () => {
    const out = serializeThreadMessages([
      { role: 'user', content: [{ type: 'text', text: 'hello' }] },
      { role: 'assistant', content: [{ type: 'text', text: 'hi' }], metadata: { custom: { confidence: 'low' } } },
    ]);
    expect(out).toEqual([
      expect.objectContaining({ role: 'user', content: 'hello' }),
      expect.objectContaining({ role: 'assistant', content: 'hi' }),
    ]);
  });

  it('createEmptySession yields unique ids', () => {
    const a = createEmptySession();
    const b = createEmptySession();
    expect(a.id).not.toBe(b.id);
  });
});
