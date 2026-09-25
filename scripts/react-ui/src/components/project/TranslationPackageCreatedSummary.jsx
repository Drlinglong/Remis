import React from 'react';
import { Alert, Stack, Text } from '@mantine/core';

const formatBytes = (bytes, locale) => new Intl.NumberFormat(locale).format(Math.max(0, Number(bytes) || 0));

export default function TranslationPackageCreatedSummary({ result, t, locale }) {
  if (!result) return null;

  return (
    <Alert color="teal" title={t('mars_translation_package.created_title')}>
      <Stack gap="xs">
        <Text size="sm" style={{ overflowWrap: 'anywhere' }}>{result.package_path}</Text>
        <Text size="sm">
          {t('mars_translation_package.created_summary', {
            count: result.files?.length || 0,
            bytes: formatBytes(result.size_bytes, locale),
          })}
        </Text>
        <Text size="sm">{t('mars_translation_package.installation_guidance')}</Text>
        <Text size="sm">{t('mars_translation_package.runtime_unverified')}</Text>
        <ol>{(result.installation_steps || []).map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol>
      </Stack>
    </Alert>
  );
}
