import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
  useMessage,
  useThread,
} from '@assistant-ui/react';
import { ActionIcon, Badge, Button, Group, Stack, Text, Tooltip } from '@mantine/core';
import { IconSend, IconSparkles } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';
import { sendCopilotChat } from '../../services/copilotService';
import { buildWorkflowCompletionMessage, serializeThreadMessages } from '../../services/copilotSessionStore';
import { useCopilotActions } from '../../hooks/useCopilotActions';
import { useTranslationContext } from '../../context/TranslationContextCore';
import styles from './RemisCopilotThread.module.css';
import InlineLocalizationWorkflow from './InlineLocalizationWorkflow';

function extractTextFromParts(parts) {
  if (!Array.isArray(parts)) {
    return '';
  }
  return parts
    .filter((part) => part && part.type === 'text' && typeof part.text === 'string')
    .map((part) => part.text)
    .join('\n')
    .trim();
}

function threadMessagesToApi(messages) {
  return (messages || [])
    .map((msg) => {
      const role = msg.role === 'assistant' ? 'assistant' : msg.role === 'system' ? 'system' : 'user';
      const content = extractTextFromParts(msg.content);
      if (!content) {
        return null;
      }
      return { role, content };
    })
    .filter(Boolean);
}

function MessageActionsBar({ onAction }) {
  const { t } = useTranslation();
  const custom = useMessage((m) => m.metadata?.custom);
  const role = useMessage((m) => m.role);
  const actions = Array.isArray(custom?.suggested_actions) ? custom.suggested_actions : [];
  const sources = Array.isArray(custom?.sources) ? custom.sources : [];
  const confidence = custom?.confidence;
  const grounding = custom?.grounding;

  if (role !== 'assistant') {
    return null;
  }

  return (
    <Stack gap={6} mt="xs" className={styles.actionBar}>
      {actions.length > 0 && (
        <Group gap="xs" wrap="wrap">
          {actions.map((item) => (
            <Button
              key={item.action}
              size="xs"
              variant="light"
              onClick={() => onAction(item)}
            >
              {item.label || item.action}
            </Button>
          ))}
        </Group>
      )}
      {(sources.length > 0 || confidence || grounding) && (
        <Group gap="xs" wrap="wrap">
          {confidence && (
            <Badge
              size="sm"
              variant="outline"
              color={confidence === 'low' ? 'orange' : confidence === 'high' ? 'green' : 'gray'}
            >
              {t('copilot.confidence', '置信度')}: {confidence}
            </Badge>
          )}
          {grounding && (
            <Badge
              size="sm"
              variant="light"
              color={
                grounding === 'none'
                  ? 'red'
                  : grounding === 'weak'
                    ? 'yellow'
                    : grounding === 'policy'
                      ? 'violet'
                      : 'teal'
              }
            >
              {t('copilot.grounding', '文档依据')}: {grounding}
            </Badge>
          )}
          {sources.slice(0, 3).map((src) => (
            <Badge key={src.path || src.title} size="sm" variant="dot" color="blue">
              {src.title || src.path}
            </Badge>
          ))}
        </Group>
      )}
    </Stack>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className={`${styles.message} ${styles.userMessage}`}>
      <div className={styles.bubble}>
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage({ onAction }) {
  return (
    <MessagePrimitive.Root className={`${styles.message} ${styles.assistantMessage}`}>
      <div className={styles.bubble}>
        <MessagePrimitive.Parts
          components={{
            Text: ({ text }) => (
              <div className={styles.markdown}>
                <ReactMarkdown>{text}</ReactMarkdown>
              </div>
            ),
          }}
        />
        <MessageActionsBar onAction={onAction} />
      </div>
    </MessagePrimitive.Root>
  );
}

function EmptyState({ onSuggestion }) {
  const { t } = useTranslation();
  const suggestions = [
    t('copilot.suggestion_first_run', '第一次汉化该怎么走？'),
    t('copilot.suggestion_api', '怎么配置 LM Studio / API？'),
    t('copilot.suggestion_deploy', '翻译完如何部署进游戏？'),
    t('copilot.suggestion_logs', '报错了，日志在哪里？'),
  ];

  return (
    <div className={styles.empty}>
      <IconSparkles size={36} stroke={1.4} className={styles.emptyIcon} />
      <Text fw={600} size="lg">
        {t('copilot.empty_title', 'Remis 小助手')}
      </Text>
      <Text c="dimmed" size="sm" maw={480} ta="center">
        {t(
          'copilot.empty_desc',
          '问我如何使用 Remis。测试阶段默认走本地 LM Studio。我可以解释流程，并给出可点击的页面跳转建议。',
        )}
      </Text>
      <Group gap="xs" mt="md" justify="center" wrap="wrap">
        {suggestions.map((text) => (
          <Button key={text} size="xs" variant="default" onClick={() => onSuggestion(text)}>
            {text}
          </Button>
        ))}
      </Group>
    </div>
  );
}

/** Persist assistant-ui messages into the session store. */
function MessagePersister({ sessionId, onMessagesChange }) {
  const messages = useThread((t) => t.messages);
  const lastSerialized = useRef('');

  useEffect(() => {
    if (!sessionId || !onMessagesChange) {
      return undefined;
    }
    // Skip running status flicker: still serialize so reloads keep partial progress.
    const serialized = serializeThreadMessages(messages);
    const fingerprint = JSON.stringify(serialized);
    if (fingerprint === lastSerialized.current) {
      return undefined;
    }
    lastSerialized.current = fingerprint;
    onMessagesChange(sessionId, serialized);
    return undefined;
  }, [messages, onMessagesChange, sessionId]);

  return null;
}

/**
 * assistant-ui Thread wired to Remis /api/copilot/chat.
 * Remount with key={sessionId} when switching sessions.
 */
export default function RemisCopilotThread({
  sessionId,
  initialMessages = [],
  onMessagesChange,
  provider = 'lm_studio',
  model = null,
  locale = 'zh',
  pageContext = null,
}) {
  const { t } = useTranslation();
  const { runAction } = useCopilotActions();
  const {
    setActiveStep,
    setIsProcessing,
    setSelectedProjectId,
    setTaskId,
    setTranslationDetails,
  } = useTranslationContext();
  const [actionError, setActionError] = useState('');
  const [contextNote, setContextNote] = useState('');
  const [workflowArgs, setWorkflowArgs] = useState(null);

  const chatModel = useMemo(
    () => ({
      async run({ messages, abortSignal }) {
        const apiMessages = threadMessagesToApi(messages);
        const data = await sendCopilotChat({
          messages: apiMessages,
          provider,
          model,
          locale,
          pageContext,
          signal: abortSignal,
        });

        const reply = data?.reply || t('copilot.empty_reply', '（没有回复）');
        const dropped = data?.context?.dropped_message_count || 0;
        if (dropped > 0) {
          setContextNote(
            t('copilot.context_trimmed', '已为适配本地模型上下文，省略了较早的 {{count}} 条消息', {
              count: dropped,
            }),
          );
        }

        return {
          content: [{ type: 'text', text: reply }],
          metadata: {
            custom: {
              suggested_actions: data?.suggested_actions || [],
              sources: data?.sources || [],
              confidence: data?.confidence,
              grounding: data?.grounding,
              grounding_score: data?.grounding_score,
              parse_mode: data?.parse_mode,
              provider: data?.provider,
              context: data?.context,
            },
          },
        };
      },
    }),
    [locale, model, pageContext, provider, t],
  );

  const runtime = useLocalRuntime(chatModel, {
    initialMessages: initialMessages || [],
  });

  const handleAction = useCallback(
    async (item) => {
      setActionError('');
      try {
        if (item.action === 'start_localization_workflow') {
          setWorkflowArgs(item.args || {});
          return;
        }
        await runAction(item.action, item.args || {});
      } catch (err) {
        console.error(err);
        setActionError(err?.message || String(err));
      }
    },
    [runAction],
  );

  const handleSuggestion = useCallback(
    (text) => {
      runtime.thread.append(text);
    },
    [runtime],
  );

  const handleWorkflowStarted = useCallback((workflow) => {
    setTaskId(workflow.taskId);
    setSelectedProjectId(workflow.projectId);
    setTranslationDetails({
      projectId: workflow.projectId,
      modName: workflow.projectName,
      provider: workflow.provider,
      model: workflow.model,
      sourceLang: workflow.sourceLanguage,
      targetLangs: [workflow.targetLanguage],
      gameId: workflow.gameId,
    });
    setIsProcessing(true);
    setActiveStep(2);
    runtime.thread.append(buildWorkflowCompletionMessage(workflow));
    setWorkflowArgs(null);
  }, [runtime, setActiveStep, setIsProcessing, setSelectedProjectId, setTaskId, setTranslationDetails]);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <MessagePersister sessionId={sessionId} onMessagesChange={onMessagesChange} />
      <div className={styles.threadShell}>
        <ThreadPrimitive.Root className={styles.threadRoot}>
          <ThreadPrimitive.Viewport className={styles.viewport}>
            <ThreadPrimitive.Empty>
              <EmptyState onSuggestion={handleSuggestion} />
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{
                UserMessage,
                AssistantMessage: () => <AssistantMessage onAction={handleAction} />,
              }}
            />
          </ThreadPrimitive.Viewport>

          {workflowArgs && (
            <InlineLocalizationWorkflow
              initialArgs={workflowArgs}
              onClose={() => setWorkflowArgs(null)}
              onStarted={handleWorkflowStarted}
            />
          )}

          {contextNote && (
            <Text c="dimmed" size="xs" px="md" py={2}>
              {contextNote}
            </Text>
          )}

          {actionError && (
            <Text c="red" size="xs" px="md" py={4}>
              {actionError}
            </Text>
          )}

          <ComposerPrimitive.Root className={styles.composer}>
            <ComposerPrimitive.Input
              className={styles.composerInput}
              placeholder={t('copilot.input_placeholder', '问问怎么用 Remis…')}
              rows={1}
            />
            <ComposerPrimitive.Send asChild>
              <Tooltip label={t('copilot.send', '发送')}>
                <ActionIcon size="lg" variant="filled" color="blue" radius="md" aria-label="send">
                  <IconSend size={18} />
                </ActionIcon>
              </Tooltip>
            </ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
        </ThreadPrimitive.Root>
      </div>
    </AssistantRuntimeProvider>
  );
}
