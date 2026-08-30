/**
 * Browser-local multi-session store for Remis Copilot.
 * Persists across route changes and app reloads (localStorage).
 */

const STORAGE_KEY = 'remis_copilot_sessions_v1';
const MAX_SESSIONS = 40;
const MAX_MESSAGES_PER_SESSION = 200;

function nowIso() {
  return new Date().toISOString();
}

function createId() {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi?.randomUUID) {
    return cryptoApi.randomUUID();
  }
  if (cryptoApi?.getRandomValues) {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    const randomHex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return `sess_${randomHex}`;
  }
  throw new Error('Secure random generation is unavailable in this WebView');
}

export function createEmptySession(partial = {}) {
  const ts = nowIso();
  return {
    id: partial.id || createId(),
    title: partial.title || '',
    createdAt: partial.createdAt || ts,
    updatedAt: partial.updatedAt || ts,
    messages: Array.isArray(partial.messages) ? partial.messages : [],
  };
}

function defaultState() {
  const session = createEmptySession({ title: '' });
  return {
    version: 1,
    activeSessionId: session.id,
    sessions: [session],
  };
}

export function loadCopilotState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaultState();
    }
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.sessions) || parsed.sessions.length === 0) {
      return defaultState();
    }
    const sessions = parsed.sessions
      .map((s) => createEmptySession(s))
      .filter((s) => s.id);
    if (sessions.length === 0) {
      return defaultState();
    }
    let activeSessionId = parsed.activeSessionId;
    if (!sessions.some((s) => s.id === activeSessionId)) {
      activeSessionId = sessions[0].id;
    }
    return { version: 1, activeSessionId, sessions };
  } catch (err) {
    console.warn('[copilot] failed to load sessions', err);
    return defaultState();
  }
}

export function saveCopilotState(state) {
  try {
    const sessions = (state.sessions || [])
      .slice(0, MAX_SESSIONS)
      .map((s) => ({
        ...s,
        messages: (s.messages || []).slice(-MAX_MESSAGES_PER_SESSION),
      }));
    const payload = {
      version: 1,
      activeSessionId: state.activeSessionId,
      sessions,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    return payload;
  } catch (err) {
    console.warn('[copilot] failed to save sessions', err);
    return state;
  }
}

export function getSession(state, sessionId) {
  return (state.sessions || []).find((s) => s.id === sessionId) || null;
}

export function upsertSessionMessages(state, sessionId, messages, { titleFromFirstUser = true } = {}) {
  const sessions = (state.sessions || []).map((s) => {
    if (s.id !== sessionId) {
      return s;
    }
    const next = {
      ...s,
      messages: (messages || []).slice(-MAX_MESSAGES_PER_SESSION),
      updatedAt: nowIso(),
    };
    if (titleFromFirstUser) {
      const firstUser = next.messages.find((m) => m.role === 'user' && m.content);
      if (firstUser?.content) {
        const t = String(firstUser.content).replace(/\s+/g, ' ').trim();
        next.title = t.length > 36 ? `${t.slice(0, 36)}…` : t;
      }
    }
    return next;
  });
  return saveCopilotState({ ...state, sessions });
}

/** Add/update a session without stealing the full-page active selection. */
export function upsertBackgroundSessionMessages(state, session, messages) {
  if (!session?.id) {
    return state;
  }
  const exists = getSession(state, session.id);
  if (exists) {
    return upsertSessionMessages(state, session.id, messages);
  }
  const retainedSessions = (state.sessions || [])
    .filter((storedSession) => (storedSession.messages || []).length > 0);
  const activeSessionSurvives = retainedSessions
    .some((storedSession) => storedSession.id === state.activeSessionId);
  const seeded = {
    ...state,
    activeSessionId: activeSessionSurvives ? state.activeSessionId : session.id,
    sessions: [
      { ...session, messages: [] },
      ...retainedSessions,
    ],
  };
  return upsertSessionMessages(seeded, session.id, messages);
}

export function createSessionInState(state) {
  const session = createEmptySession();
  const sessions = [session, ...(state.sessions || [])].slice(0, MAX_SESSIONS);
  return saveCopilotState({
    ...state,
    activeSessionId: session.id,
    sessions,
  });
}

export function deleteSessionInState(state, sessionId) {
  let sessions = (state.sessions || []).filter((s) => s.id !== sessionId);
  if (sessions.length === 0) {
    const fresh = createEmptySession();
    return saveCopilotState({
      version: 1,
      activeSessionId: fresh.id,
      sessions: [fresh],
    });
  }
  let activeSessionId = state.activeSessionId;
  if (activeSessionId === sessionId) {
    activeSessionId = sessions[0].id;
  }
  return saveCopilotState({ ...state, activeSessionId, sessions });
}

export function setActiveSessionInState(state, sessionId) {
  if (!(state.sessions || []).some((s) => s.id === sessionId)) {
    return state;
  }
  return saveCopilotState({ ...state, activeSessionId: sessionId });
}

/** Convert assistant-ui thread messages → plain store messages. */
export function serializeThreadMessages(messages) {
  if (!Array.isArray(messages)) {
    return [];
  }
  return messages
    .map((msg) => {
      const role = msg.role === 'assistant' ? 'assistant' : msg.role === 'system' ? 'system' : 'user';
      let content = '';
      if (typeof msg.content === 'string') {
        content = msg.content;
      } else if (Array.isArray(msg.content)) {
        content = msg.content
          .filter((p) => p && p.type === 'text' && typeof p.text === 'string')
          .map((p) => p.text)
          .join('\n')
          .trim();
      }
      if (!content) {
        return null;
      }
      const custom = msg.metadata?.custom;
      return {
        id: msg.id,
        role,
        content,
        createdAt: msg.createdAt ? new Date(msg.createdAt).toISOString() : undefined,
        metadata: custom ? { custom } : undefined,
      };
    })
    .filter(Boolean);
}

/** Store messages → assistant-ui initialMessages (ThreadMessageLike). */
export function toInitialMessages(storedMessages) {
  if (!Array.isArray(storedMessages)) {
    return [];
  }
  return storedMessages
    .filter((m) => m && m.content && (m.role === 'user' || m.role === 'assistant'))
    .map((m) => {
      const restoredCreatedAt = m.createdAt ? new Date(m.createdAt) : null;
      const hasValidCreatedAt = restoredCreatedAt && Number.isFinite(restoredCreatedAt.getTime());
      return {
        id: m.id,
        role: m.role,
        content: m.content,
        ...(hasValidCreatedAt ? { createdAt: restoredCreatedAt } : {}),
        ...(m.metadata?.custom
          ? { metadata: { custom: m.metadata.custom } }
          : {}),
      };
    });
}

export function buildWorkflowCompletionMessage(workflow) {
  const projectName = workflow.projectName || '未命名项目';
  const targetLanguage = (workflow.targetLanguages || [workflow.targetLanguage]).filter(Boolean).join('、') || '未指定';
  const sourceLanguage = workflow.sourceLanguage || '未指定';
  const enhancements = [
    workflow.useResume && '断点续传',
    workflow.useMainGlossary && '主词典',
    workflow.workshopEnabled && '格式修复台',
  ].filter(Boolean);
  const text = [
    '### 已批准并启动翻译',
    '',
    `- **项目：** ${projectName}`,
    `- **项目 ID：** \`${workflow.projectId}\``,
    `- **任务 ID：** \`${workflow.taskId}\``,
    `- **游戏：** ${workflow.gameId}`,
    `- **语言：** ${sourceLanguage} → ${targetLanguage}`,
    `- **Provider / 模型：** ${workflow.provider} / ${workflow.model}`,
    `- **限流：** Batch ${workflow.batchSize}，并发 ${workflow.concurrency}，RPM ${workflow.rpm}`,
    `- **增强：** ${enhancements.join('、') || '无'}`,
    '',
    '我已经保存了这次操作记录，并会在后续对话中把它作为上下文。你可以随时查看翻译进度。',
  ].join('\n');

  return {
    role: 'assistant',
    content: [{ type: 'text', text }],
    metadata: {
      custom: {
        workflow,
        suggested_actions: [{
          action: 'open_initial_translation',
          label: '查看翻译进度',
          args: { task_id: workflow.taskId, project_id: workflow.projectId },
        }],
      },
    },
  };
}
