import React from 'react';
import { Alert, Badge, Button, Card, Group, Stack, Text, Title } from '@mantine/core';

import styles from './ProjectDetailSurfaces.module.css';

const formatBytes = (bytes, locale) => new Intl.NumberFormat(locale).format(Math.max(0, Number(bytes) || 0));

export default function TranslationPackagePreview({ plan, packageFlow, t, locale }) {
  const packageInfo = plan.package || {};
  const files = Array.isArray(packageInfo.files) ? packageInfo.files : [];
  return (
    <Card data-remis-surface="paper" className={styles.paperInset} withBorder>
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Title order={4}>{t('mars_translation_package.preview_title')}</Title>
          <Badge variant="light">{t('mars_translation_package.requires_approval')}</Badge>
        </Group>
        <Text>{plan.summary}</Text>
        <Text size="sm">
          {t('mars_translation_package.package_summary', {
            modId: packageInfo.mod_id || '',
            title: packageInfo.title || '',
            language: packageInfo.language || '',
            count: files.length,
            bytes: formatBytes(packageInfo.total_size_bytes, locale),
          })}
        </Text>
        <Stack gap={4}>
          {files.map((file) => (
            <Group key={file.path} justify="space-between" gap="sm" wrap="wrap">
              <Text size="sm" style={{ overflowWrap: 'anywhere' }}>{file.path}</Text>
              <Text size="xs" c="dimmed">{formatBytes(file.size_bytes, locale)} B</Text>
            </Group>
          ))}
        </Stack>
        {(plan.warnings || []).map((warning, index) => (
          <Alert key={`${index}-${warning}`} color="yellow">{warning}</Alert>
        ))}
        <Text fw={600}>{t('mars_translation_package.installation_title')}</Text>
        <Text size="sm" c="dimmed">{t('mars_translation_package.installation_guidance')}</Text>
        <ol>{(plan.installation_steps || []).map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol>
        <Text size="sm" c="dimmed">{t('mars_translation_package.write_approval')}</Text>
        <Button
          color="teal"
          onClick={packageFlow.generatePackage}
          loading={packageFlow.generating}
          disabled={packageFlow.generating || files.length === 0}
        >
          {t('mars_translation_package.generate')}
        </Button>
      </Stack>
    </Card>
  );
}
