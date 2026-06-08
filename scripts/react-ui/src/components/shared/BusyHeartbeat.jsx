import React from 'react';
import { Box, Group, Loader, Stack, Text } from '@mantine/core';
import styles from './BusyHeartbeat.module.css';

const BusyHeartbeat = ({
  active,
  title,
  description,
  color = 'blue',
  compact = false,
}) => {
  if (!active) return null;

  return (
    <Box className={compact ? styles.compactShell : styles.shell} data-color={color}>
      <Group gap="sm" wrap="nowrap" align="center">
        <Box className={styles.loaderWrap}>
          <Loader size={compact ? 'sm' : 'md'} type="dots" color={color} />
        </Box>
        <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
          {title && (
            <Text size={compact ? 'sm' : 'md'} fw={700} truncate>
              {title}
            </Text>
          )}
          {description && (
            <Text size="xs" c="dimmed" lineClamp={2}>
              {description}
            </Text>
          )}
        </Stack>
        <Group gap={4} className={styles.beats} wrap="nowrap" aria-hidden="true">
          <span />
          <span />
          <span />
        </Group>
      </Group>
      <Box className={styles.shimmer} />
    </Box>
  );
};

export default BusyHeartbeat;
