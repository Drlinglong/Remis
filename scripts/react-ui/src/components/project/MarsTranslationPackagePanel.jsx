import React, { useState } from 'react';
import { Button, Card, Group, Text, Title } from '@mantine/core';
import { IconPackageExport } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { useTranslationPackage } from '../../hooks/useTranslationPackage';
import MarsTranslationPackageDialog from './MarsTranslationPackageDialog';
import TranslationPackageCreatedSummary from './TranslationPackageCreatedSummary';
import styles from './ProjectDetailSurfaces.module.css';

export default function MarsTranslationPackagePanel({ projectId, gameId }) {
  const { t, i18n } = useTranslation();
  const [opened, setOpened] = useState(false);
  const packageFlow = useTranslationPackage(projectId, gameId);
  const result = packageFlow.result;

  if (gameId !== 'surviving_mars') return null;

  return (
    <Card
      id="mars-translation-package-panel"
      data-remis-surface="paper"
      className={styles.paperPanel}
      withBorder
      p="md"
    >
      <Group justify="space-between" align="center" wrap="wrap">
        <div>
          <Title order={3}>{t('mars_translation_package.title')}</Title>
          <Text size="sm" c="dimmed">{t('mars_translation_package.description')}</Text>
        </div>
        <Button
          leftSection={<IconPackageExport size={16} />}
          onClick={() => setOpened(true)}
          disabled={packageFlow.loading}
          loading={packageFlow.loading}
        >
          {t('mars_translation_package.open')}
        </Button>
      </Group>

      {packageFlow.loading && <Text mt="sm" size="sm" role="status">{t('mars_translation_package.loading')}</Text>}
      {result && <TranslationPackageCreatedSummary result={result} t={t} locale={i18n.language} />}

      <MarsTranslationPackageDialog
        opened={opened}
        onClose={() => setOpened(false)}
        packageFlow={packageFlow}
        t={t}
        locale={i18n.language}
      />
    </Card>
  );
}
