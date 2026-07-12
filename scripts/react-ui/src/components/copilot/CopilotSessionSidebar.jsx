import React from 'react';
import { ActionIcon, Button, Group, ScrollArea, Stack, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { IconMessagePlus, IconTrash } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from './CopilotSessionSidebar.module.css';

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function CopilotSessionSidebar({
  sessions = [],
  activeSessionId,
  onSelect,
  onCreate,
  onDelete,
}) {
  const { t } = useTranslation();

  return (
    <div className={styles.sidebar}>
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <Text size="sm" fw={600}>
          {t('copilot.sessions_title', '会话')}
        </Text>
        <Tooltip label={t('copilot.new_chat', '新建会话')}>
          <Button
            size="compact-xs"
            variant="light"
            leftSection={<IconMessagePlus size={14} />}
            onClick={onCreate}
          >
            {t('copilot.new_chat', '新建会话')}
          </Button>
        </Tooltip>
      </Group>

      <ScrollArea className={styles.list} type="auto" offsetScrollbars>
        <Stack gap={4}>
          {sessions.map((session) => {
            const active = session.id === activeSessionId;
            const title =
              session.title?.trim() ||
              t('copilot.untitled_chat', '新对话');
            return (
              <div
                key={session.id}
                className={`${styles.item} ${active ? styles.itemActive : ''}`}
              >
                <UnstyledButton
                  className={styles.itemButton}
                  onClick={() => onSelect(session.id)}
                  title={title}
                >
                  <Text size="sm" lineClamp={1} fw={active ? 600 : 400}>
                    {title}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {formatTime(session.updatedAt || session.createdAt)}
                  </Text>
                </UnstyledButton>
                <Tooltip label={t('copilot.delete_chat', '删除会话')}>
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="red"
                    className={styles.deleteBtn}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(session.id);
                    }}
                    aria-label="delete-session"
                  >
                    <IconTrash size={14} />
                  </ActionIcon>
                </Tooltip>
              </div>
            );
          })}
        </Stack>
      </ScrollArea>
    </div>
  );
}
