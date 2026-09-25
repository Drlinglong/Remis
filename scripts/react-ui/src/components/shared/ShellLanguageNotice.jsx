import React from 'react';
import { Alert, Text } from '@mantine/core';

export default function ShellLanguageNotice({ t, compact = false }) {
  return (
    <Alert color="blue" variant="light" my="xs">
      {!compact && <Text size="sm">{t('shell_language_notice.recommendation')}</Text>}
      <details>
        <summary style={{ cursor: 'pointer' }}>
          {t(compact ? 'shell_language_notice.detected' : 'shell_language_notice.learn_more')}
        </summary>
        <Text size="sm" mt="xs">{t('shell_language_notice.explanation')}</Text>
      </details>
    </Alert>
  );
}
