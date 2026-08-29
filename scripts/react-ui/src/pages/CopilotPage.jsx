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
 * Provider/model/reasoning are resolved from the shared server settings.
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
              Agent Preview
            </Badge>
          </Group>
          <Text c="dimmed" size="sm">
            {t(
              'copilot.preview_subtitle',
              '基于白名单用户文档和当前页面上下文回答，并提供 approval-gated Workflow Agent。',
            )}
          </Text>
        </div>
        <Group gap="xs">
          <Badge variant="outline" color="cyan">
            {t('copilot.provider_label', '供应商')}: {status?.default_provider || 'lm_studio'}
          </Badge>
          <Badge variant="outline" color="blue">
            {t('copilot.model_label', '模型')}: {status?.default_model || 'local-model'}
          </Badge>
          <Badge variant="outline" color={status?.reasoning_enabled ? 'grape' : 'gray'}>
            {t('copilot.reasoning_label', '推理')}:{' '}
            {status?.reasoning_enabled ? status.reasoning_preset : t('copilot.reasoning_off', '关闭')}
          </Badge>
          <Badge variant="outline" color="gray">
            {t('copilot.context_budget_badge', '上下文预算')}:{' '}
            {status?.context_budget_tokens || 200000} tokens
          </Badge>
        </Group>
      </Group>

      <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
        {t(
          'copilot.preview_notice',
          '会话保存在本机。供应商、模型和推理强度由“设置 → 小助手设置”统一管理；文档未覆盖的问题会强制低置信，批准前不会执行付费或写入操作。',
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
                locale={locale}
              />
            )}
          </div>
        </div>
      </Paper>
    </Stack>
  );
}
