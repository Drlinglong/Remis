import React from 'react';
import { Alert, Anchor, Divider, Group, List, Paper, Stack, Text, ThemeIcon } from '@mantine/core';
import { IconBrandBilibili, IconBrandYoutube, IconInfoCircle, IconTrophy } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';

const ExternalLink = ({ url, children }) => {
  const { t } = useTranslation();
  const openLink = async (event) => {
    event.preventDefault();
    try {
      const { open } = await import('@tauri-apps/plugin-shell');
      await open(url);
    } catch (error) {
      console.warn('Tauri shell unavailable; using browser fallback.', error);
      if (!window.open(url, '_blank')) {
        notifications.show({
          title: t('error'),
          message: t('api_external_link_blocked'),
          color: 'red',
        });
      }
    }
  };

  return (
    <Anchor component="button" type="button" onClick={openLink} size="sm">
      {children}
    </Anchor>
  );
};

const ApiResourceGuides = () => {
  const { t } = useTranslation();
  return (
    <>
      <Paper data-remis-surface="paper" withBorder p="md" radius="md">
        <Group align="flex-start" wrap="nowrap">
          <ThemeIcon size="xl" radius="xl" variant="filled" color="violet">
            <IconTrophy size={22} />
          </ThemeIcon>
          <Stack gap={4}>
            <Text fw={700}>{t('api_aventine_title')}</Text>
            <Text size="sm">{t('api_aventine_description')}</Text>
            <ExternalLink url="https://drlinglong.github.io/Remis/aventine/">
              {t('api_aventine_action')}
            </ExternalLink>
          </Stack>
        </Group>
      </Paper>

      <Alert id="api-storage-info" variant="light" color="blue" title={t('api_configuration_title')} icon={<IconInfoCircle />}>
        <Stack gap="xs">
          <Text size="sm">{t('api_settings_storage_info')}</Text>
          <Divider variant="dashed" />
          <Group gap="xs">
            <IconBrandBilibili size={16} />
            <Text size="sm" fw={500}>Bilibili {t('api_guide_video_tutorial')}:</Text>
          </Group>
          <List size="sm" type="ordered" withPadding>
            <List.Item><ExternalLink url="https://www.bilibili.com/video/BV1LEKMexEV7/">{t('api_guide_video_deepseek_title')}</ExternalLink></List.Item>
            <List.Item><ExternalLink url="https://www.bilibili.com/video/BV1FRuTzwEig/">{t('api_guide_video_beginner_title')}</ExternalLink></List.Item>
          </List>
          <Divider variant="dashed" />
          <Group gap="xs">
            <IconBrandYoutube size={16} />
            <Text size="sm" fw={500}>YouTube {t('api_guide_video_tutorial')}:</Text>
          </Group>
          <List size="sm" type="ordered" withPadding>
            <List.Item><ExternalLink url="https://www.youtube.com/watch?v=OB99E7Y1cMA">{t('api_guide_video_desc_1')}</ExternalLink></List.Item>
            <List.Item><ExternalLink url="https://www.youtube.com/watch?v=6BRyynZkvf0">{t('api_guide_video_desc_2')}</ExternalLink></List.Item>
          </List>
          <Text size="xs" c="dimmed" mt="xs">{t('api_guide_disclaimer')}</Text>
        </Stack>
      </Alert>
    </>
  );
};

export default ApiResourceGuides;
