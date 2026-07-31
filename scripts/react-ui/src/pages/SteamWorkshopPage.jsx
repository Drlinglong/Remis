import React from 'react';
import { Container, Paper } from '@mantine/core';
import { useParams } from 'react-router';

import layoutStyles from '../components/layout/Layout.module.css';
import SteamWorkshopOverview from '../components/steamWorkshop/SteamWorkshopOverview';
import SteamWorkshopWorkspace from '../components/steamWorkshop/SteamWorkshopWorkspace';

export default function SteamWorkshopPage() {
  const { workspaceId, section } = useParams();

  return (
    <Container data-remis-surface="canvas" size="xl" py="xl">
      <Paper data-remis-surface="surface" withBorder p="xl" radius="md" className={layoutStyles.glassCard}>
        {workspaceId ? (
          <SteamWorkshopWorkspace activeSection={section} workspaceId={workspaceId} />
        ) : (
          <SteamWorkshopOverview />
        )}
      </Paper>
    </Container>
  );
}
