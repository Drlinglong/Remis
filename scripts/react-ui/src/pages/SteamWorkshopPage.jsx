import React, { useEffect, useState } from 'react';
import {
  Button,
  Container,
  Group,
  Modal,
  Paper,
  Stack,
  Text,
} from '@mantine/core';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';

import layoutStyles from '../components/layout/Layout.module.css';
import SteamWorkshopOverview from '../components/steamWorkshop/SteamWorkshopOverview';
import SteamWorkshopWorkspace from '../components/steamWorkshop/SteamWorkshopWorkspace';
import { getTutorialKey, useTutorial } from '../context/TutorialContextCore';

export default function SteamWorkshopPage() {
  const { workspaceId, section } = useParams();
  const { t } = useTranslation();
  const { setPageContext, startTour } = useTutorial();
  const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);
  const tutorialContext = workspaceId
    ? `steam-workshop-${['cover', 'description', 'history'].includes(section) ? section : 'cover'}`
    : 'steam-workshop';

  useEffect(() => {
    setPageContext(tutorialContext);
    if (!workspaceId && !localStorage.getItem(getTutorialKey('steam-workshop_prompt_seen'))) {
      setShowTutorialPrompt(true);
    }
  }, [setPageContext, tutorialContext, workspaceId]);

  const dismissTutorialPrompt = () => {
    setShowTutorialPrompt(false);
    localStorage.setItem(getTutorialKey('steam-workshop_prompt_seen'), 'true');
  };

  return (
    <Container id="steam-workshop-page" data-remis-surface="canvas" size="xl" py="xl">
      <Paper
        id="steam-workshop-content"
        data-remis-surface="surface"
        withBorder
        p="xl"
        radius="md"
        className={layoutStyles.glassCard}
      >
        {workspaceId ? (
          <SteamWorkshopWorkspace activeSection={section} workspaceId={workspaceId} />
        ) : (
          <SteamWorkshopOverview />
        )}
      </Paper>
      <Modal
        opened={showTutorialPrompt}
        onClose={dismissTutorialPrompt}
        title={t('tutorial.auto_start_prompt.title')}
        centered
        radius="md"
      >
        <Stack>
          <Text size="sm">{t('tutorial.steam_workshop.prompt.message')}</Text>
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" color="gray" onClick={dismissTutorialPrompt}>
              {t('tutorial.auto_start_prompt.cancel')}
            </Button>
            <Button
              onClick={() => {
                dismissTutorialPrompt();
                startTour(tutorialContext);
              }}
            >
              {t('tutorial.auto_start_prompt.confirm')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
