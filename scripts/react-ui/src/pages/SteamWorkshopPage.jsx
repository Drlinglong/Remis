import React from 'react';
import { Container, Paper } from '@mantine/core';

import layoutStyles from '../components/layout/Layout.module.css';
import SteamWorkshopWorkspace from '../components/steamWorkshop/SteamWorkshopWorkspace';

export default function SteamWorkshopPage({ projectId = null }) {
  return (
    <Container data-remis-surface="canvas" size="xl" py="xl">
      <Paper data-remis-surface="surface" withBorder p="xl" radius="md" className={layoutStyles.glassCard}>
        <SteamWorkshopWorkspace projectId={projectId} />
      </Paper>
    </Container>
  );
}
