import React from 'react';
import { Box, Button, Paper, Stack, Text, Title } from '@mantine/core';
import MarsPipelineImport from '../components/project/MarsPipelineImport';
import styles from './VisualReliabilityLab.module.css';

const controller = {
  path: String.raw`I:\SteamLibrary\steamapps\workshop\content\3215050\ModContent.fpk`,
  name: 'Exotic Minerals Expanded — 中文本地化',
  previousRun: '',
  deliveryMode: 'source_copy',
  approved: ['1', '2'],
  plan: {
    file_count: 57,
    entry_count: 88,
    selected_entry_count: 47,
    hardcoded_entry_count: 41,
    recommended_delivery_mode: 'source_copy',
    selected_delivery_mode: 'source_copy',
    review_items: [
      { id: '812345', text: 'A long source phrase that needs human review before it is included in the complete translated Mod copy.', reason: 'Translation context is unclear.', refs: [{ path: 'Lua/Events/Intro.lua', line: 42 }] },
      { id: '812346', text: 'Dynamic mineral discovery text', reason: 'Expression uses a runtime value.', refs: [{ path: 'Lua/Events/Discovery.lua', line: 18 }] },
    ],
  },
  inspection: {
    file_count: 57,
    entry_count: 88,
    selected_entry_count: 47,
    hardcoded_entry_count: 41,
    recommended_delivery_mode: 'source_copy',
    selected_delivery_mode: 'source_copy',
  },
  busy: false,
  error: '',
  update: () => {},
  preview: () => {},
  execute: () => {},
};

export default function MarsPipelineVisualFixture() {
  return (
    <Box className={styles.page} data-remis-surface="canvas"
      data-testid="mars-pipeline-visual-fixture" data-visual-ready="true">
      <Paper data-remis-surface="paper" p="lg" radius="md" withBorder>
        <Stack gap="sm">
          <Title order={2}>Surviving Mars compiled Mod preparation</Title>
          <Text>Static presentation fixture. Buttons are disconnected from archive and project services.</Text>
          <Button variant="light">Choose game: Surviving Mars / Relaunched</Button>
          <MarsPipelineImport opened name="Exotic Minerals Expanded — 中文本地化"
            onClose={() => {}} onUseExistingCsv={() => {}} controller={controller} />
        </Stack>
      </Paper>
    </Box>
  );
}
