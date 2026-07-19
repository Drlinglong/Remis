import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Badge, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { IconRobot, IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import RemisCopilotThread from '../components/copilot/RemisCopilotThread';
import CopilotSessionSidebar from '../components/copilot/CopilotSessionSidebar';
import { fetchCopilotStatus } from '../services/copilotService';
import {
  createSessionInState,
  deleteSessionInState,
  getSession,
  loadCopilotState,
  setActiveSessionInState,
  toInitialMessages,
  upsertSessionMessages,
} from '../services/copilotSessionStore';
import styles from './CopilotPage.module.css';

/**
 * Help Copilot page: multi-session local persistence + assistant-ui thread.
 * Provider/model picker will be added later.
 */
export default function CopilotPage() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState('');
  const [store, setStore] = useState(() => loadCopilotState());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchCopilotStatus();
        if (!cancelled) {
          setStatus(data);
        }
      } catch (err) {
        if (!cancelled) {
          setStatusError(err?.message || String(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const locale = (i18n.language || 'zh').startsWith('zh') ? 'zh' : 'en';
  const activeSession = useMemo(
    () => getSession(store, store.activeSessionId),
    [store],
  );
  const initialMessages = useMemo(
    () => toInitialMessages(activeSession?.messages || []),
    // Remount thread when session changes; don't thrash on every message persist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store.activeSessionId],
  );

  const handleMessagesChange = useCallback((sessionId, messages) => {
    setStore((prev) => upsertSessionMessages(prev, sessionId, messages));
  }, []);

  const handleCreate = useCallback(() => {
    setStore((prev) => createSessionInState(prev));
  }, []);

  const handleSelect = useCallback((sessionId) => {
    setStore((prev) => setActiveSessionInState(prev, sessionId));
  }, []);

  const handleDelete = useCallback((sessionId) => {
    setStore((prev) => deleteSessionInState(prev, sessionId));
  }, []);

  return (
    <Stack className={styles.page} gap="md">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <div>
          <Group gap="sm" mb={4}>
            <IconRobot size={28} stroke={1.5} />
            <Title order={2}>{t('page_title_copilot', 'Remis 小助手')}</Title>
            <Badge variant="light" color="grape">
              Phase 1.1
            </Badge>
          </Group>
          <Text c="dimmed" size="sm">
            {t(
              'copilot.page_subtitle',
              '帮助说明 + 可点击的安全操作建议。测试阶段默认使用本地 LM Studio。',
            )}
          </Text>
        </div>
        <Group gap="xs">
          <Badge variant="outline" color="cyan">
            {t('copilot.provider_label', '供应商')}: {status?.default_provider || 'lm_studio'}
          </Badge>
          <Badge variant="outline" color="gray">
            {t('copilot.context_budget_badge', '上下文预算')}:{' '}
            {status?.context_budget_tokens || 24000} tokens
          </Badge>
          <Badge variant="outline" color="gray">
            {t('copilot.picker_later', '模型选择器：后续版本')}
          </Badge>
        </Group>
      </Group>

      <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
        {t(
          'copilot.phase1_notice',
          '会话会保存在本机浏览器中，切换页面不会丢失。文档未覆盖的问题会强制低置信，避免瞎猜。本地模型约 32k 窗口时，过长历史会自动丢弃较早消息而不是直接报错。',
        )}
      </Alert>

      {statusError && (
        <Alert color="red" variant="light">
          {t('copilot.status_error', '无法读取助手状态')}: {statusError}
        </Alert>
      )}

      <Paper className={styles.chatPanel} withBorder radius="md" p={0}>
        <div className={styles.chatLayout}>
          <CopilotSessionSidebar
            sessions={store.sessions}
            activeSessionId={store.activeSessionId}
            onSelect={handleSelect}
            onCreate={handleCreate}
            onDelete={handleDelete}
          />
          <div className={styles.chatMain}>
            {activeSession && (
              <RemisCopilotThread
                key={activeSession.id}
                sessionId={activeSession.id}
                initialMessages={initialMessages}
                onMessagesChange={handleMessagesChange}
                provider="lm_studio"
                model={null}
                locale={locale}
              />
            )}
          </div>
        </div>
      </Paper>
    </Stack>
  );
}
