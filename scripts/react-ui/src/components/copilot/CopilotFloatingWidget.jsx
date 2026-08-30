import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActionIcon, Indicator, Paper, Text, Tooltip } from '@mantine/core';
import { IconMessageChatbot, IconX } from '@tabler/icons-react';
import { useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import RemisCopilotThread from './RemisCopilotThread';
import { useRemisCopilotContext } from '../../context/CopilotContext';
import {
  createEmptySession,
  loadCopilotState,
  toInitialMessages,
  upsertBackgroundSessionMessages,
} from '../../services/copilotSessionStore';
import styles from './CopilotFloatingWidget.module.css';

export default function CopilotFloatingWidget() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { pageContext } = useRemisCopilotContext();
  const [opened, setOpened] = useState(false);
  const [draftSession, setDraftSession] = useState(null);
  const [dismissedFingerprint, setDismissedFingerprint] = useState('');

  const initialMessages = useMemo(() => toInitialMessages(draftSession?.messages || []), [draftSession]);
  const reminder = pageContext?.reminder || null;
  const fingerprint = reminder ? `${pageContext.pageId}:${reminder.reason}:${reminder.detectedAt}` : '';
  const hasReminder = Boolean(reminder && fingerprint !== dismissedFingerprint);

  useEffect(() => {
    if (!reminder) setDismissedFingerprint('');
  }, [reminder]);

  const handleMessagesChange = useCallback((sessionId, messages) => {
    const hasUserMessage = (messages || []).some((message) => message.role === 'user' && message.content);
    if (!hasUserMessage) return;
    const latestStore = loadCopilotState();
    upsertBackgroundSessionMessages(
      latestStore,
      { ...draftSession, id: sessionId },
      messages,
    );
  }, [draftSession]);

  const handleOpen = useCallback(() => {
    // Temporary containment until Copilot sessions move to a durable per-session store:
    // floating entry points always start an ephemeral draft and persist only after user input.
    setDraftSession(createEmptySession());
    setOpened(true);
    if (fingerprint) setDismissedFingerprint(fingerprint);
  }, [fingerprint]);

  if (location.pathname === '/copilot') return null;

  const locale = (i18n.language || 'zh').startsWith('zh') ? 'zh' : 'en';
  const tooltip = hasReminder
    ? t('copilot.floating_reminder', '遇到了一些问题，不知道如何进行下一步？')
    : t('copilot.floating_open', '打开 Remis 小助手');

  return (
    <div className={styles.root}>
      {opened && draftSession && (
        <Paper className={styles.panel} shadow="xl" radius="lg" withBorder>
          <div className={styles.header}>
            <div>
              <Text fw={700}>{t('copilot.floating_title', 'Remis 小助手')}</Text>
              <Text size="xs" c="dimmed">{t('copilot.floating_subtitle', '结合当前页面告诉你下一步')}</Text>
            </div>
            <ActionIcon variant="subtle" color="gray" onClick={() => setOpened(false)} aria-label={t('common.close', '关闭')}>
              <IconX size={18} />
            </ActionIcon>
          </div>
          {reminder && (
            <div className={styles.localPrompt}>
              <Text size="sm">{reminder.openingMessage}</Text>
            </div>
          )}
          <div className={styles.thread}>
            <RemisCopilotThread
              key={draftSession.id}
              sessionId={draftSession.id}
              initialMessages={initialMessages}
              onMessagesChange={handleMessagesChange}
              locale={locale}
              pageContext={pageContext}
            />
          </div>
        </Paper>
      )}
      {!opened && (
        <Tooltip label={tooltip} position="left" withArrow>
          <Indicator disabled={!hasReminder} color="red" size={12} offset={5} processing>
            <ActionIcon className={styles.button} size={52} radius="xl" onClick={handleOpen} aria-label={tooltip}>
              <IconMessageChatbot size={27} />
            </ActionIcon>
          </Indicator>
        </Tooltip>
      )}
    </div>
  );
}
