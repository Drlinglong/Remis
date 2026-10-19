import { useState } from 'react';
import { Alert, Anchor, Button, Code, List, Paper, Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export default function PublicationSetupGuide({ runtime }) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const missing = runtime && !runtime.ready;
  return <Paper id="workshop-publication-setup" p="md" withBorder data-remis-surface="paper">
    <Stack gap="sm">
      <Button variant="default" onClick={() => setOpened((value) => !value)}
        aria-expanded={Boolean(opened || missing)}>{t('workshop_publication.setup_title')}</Button>
      {missing && <Alert color="orange">{t('workshop_publication.setup_missing')}</Alert>}
      {(opened || missing) && <>
        <List type="ordered" spacing="sm">
          <List.Item>{t('workshop_publication.setup_steam')}</List.Item>
          <List.Item>{t('workshop_publication.setup_sdk')} <Anchor href="https://partner.steamgames.com/doc/sdk"
            target="_blank" rel="noopener noreferrer">{t('workshop_publication.setup_sdk_link')}</Anchor></List.Item>
          <List.Item>{t('workshop_publication.setup_configure')}
            <Code block style={{ background: 'var(--menu-bg)', color: 'var(--menu-text)' }}>
              {'$env:REMIS_STEAM_SDK_DIR = "J:\\steamworks-sdk\\sdk"'}
            </Code>
          </List.Item>
          <List.Item>{t('workshop_publication.setup_package')}</List.Item>
          <List.Item>{t('workshop_publication.setup_upload')}</List.Item>
        </List>
        <Text size="sm">{t('workshop_publication.setup_unknown')}</Text>
      </>}
    </Stack>
  </Paper>;
}
