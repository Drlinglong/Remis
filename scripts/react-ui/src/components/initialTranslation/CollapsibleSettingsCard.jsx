import React from 'react';
import { Box, Button, Card, Group, Stack, Text, ThemeIcon } from '@mantine/core';
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react';

const sectionCardStyle = {
  background: 'linear-gradient(180deg, rgba(86, 111, 147, 0.16) 0%, rgba(41, 54, 72, 0.12) 100%)',
  border: '1px solid rgba(151, 177, 210, 0.16)',
};

export default function CollapsibleSettingsCard({
  accent,
  action,
  children,
  description,
  disabled = false,
  icon,
  isOpen,
  onToggle,
  t,
  title,
}) {
  return (
    <Card withBorder p="md" radius="lg" style={sectionCardStyle}>
      <Stack gap="sm">
        {action}
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap="sm" align="flex-start" wrap="nowrap">
            <ThemeIcon size="lg" radius="md" variant="light" color={accent}>
              {icon}
            </ThemeIcon>
            <Box>
              <Text size="sm" fw={600} c="var(--text-main)">
                {title}
              </Text>
              <Text size="xs" c="dimmed" mt={2}>
                {description}
              </Text>
            </Box>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            color={accent}
            disabled={disabled}
            rightSection={isOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
            onClick={onToggle}
          >
            {isOpen
              ? t('common.collapse', { defaultValue: '收起' })
              : t('common.expand', { defaultValue: '展开' })}
          </Button>
        </Group>
        {isOpen && (
          <Box pt="sm" style={{ borderTop: '1px solid rgba(151, 177, 210, 0.14)' }}>
            {children}
          </Box>
        )}
      </Stack>
    </Card>
  );
}
