import React from 'react';
import { Box, Button, Card, Group, Stack, Text, ThemeIcon } from '@mantine/core';
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react';

const sectionCardStyle = {
  background: 'var(--surface-bg)',
  border: '1px solid var(--surface-border)',
  color: 'var(--surface-text-main)',
  '--mantine-color-text': 'var(--surface-text-main)',
  '--mantine-color-dimmed': 'var(--surface-text-muted)',
  '--text-main': 'var(--surface-text-main)',
  '--text-muted': 'var(--surface-text-muted)',
};

export default function CollapsibleSettingsCard({
  accent,
  action,
  children,
  description,
  disabled = false,
  icon,
  isOpen,
  keepMounted = false,
  onToggle,
  t,
  title,
  toggleAriaLabel,
}) {
  return (
    <Card withBorder p="md" radius="lg" style={sectionCardStyle} data-remis-surface="surface">
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
            aria-label={toggleAriaLabel}
            rightSection={isOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
            onClick={onToggle}
          >
            {isOpen
              ? t('common.collapse', { defaultValue: '收起' })
              : t('common.expand', { defaultValue: '展开' })}
          </Button>
        </Group>
        {(isOpen || keepMounted) && (
          <Box
            pt="sm"
            data-collapsed={!isOpen || undefined}
            style={{
              borderTop: isOpen ? '1px solid var(--surface-border)' : 0,
              contentVisibility: isOpen ? 'visible' : 'hidden',
              maxHeight: isOpen ? 'none' : 0,
              opacity: isOpen ? 1 : 0,
              overflow: 'hidden',
              paddingTop: isOpen ? undefined : 0,
              pointerEvents: isOpen ? undefined : 'none',
            }}
          >
            {children}
          </Box>
        )}
      </Stack>
    </Card>
  );
}
