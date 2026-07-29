import React from 'react';
import { Container, Stack, Text, Title } from '@mantine/core';

import ConfigStep from '../components/incrementalTranslation/ConfigStep';
import ExecutionStep from '../components/incrementalTranslation/ExecutionStep';
import PreScanResultsStep from '../components/incrementalTranslation/PreScanResultsStep';
import ProjectSelectStep from '../components/incrementalTranslation/ProjectSelectStep';
import styles from '../pages/Translation.module.css';
import fixtureStyles from './IncrementalTranslationVisualLab.module.css';

const noop = () => {};
const project = {
  project_id: 'project-remis-demo',
  name: 'Project Remis - Demo Mod - Stellaris',
  game_id: 'stellaris',
  source_language: 'english',
  source_path: 'C:\\Users\\Drlin\\AppData\\Roaming\\RemisModFactoryDev\\demo\\localisation\\english',
};
const archiveInfo = {
  project_name: project.name,
  archived_languages: ['simp_chinese'],
  created_at: '2026-07-26T09:00:00Z',
  version_id: 7,
  baseline_versions: [{
    language: 'simp_chinese',
    version_id: 7,
    last_translation_at: '2026-07-25T09:00:00Z',
    created_at: '2026-07-25T09:00:00Z',
    translated_count: 128,
  }],
};

const sharedConfig = {
  archiveInfo,
  selectedProject: project,
  selectedLangs: ['simp_chinese'],
  setSelectedLangs: noop,
  selectedProvider: 'local',
  handleProviderChange: noop,
  selectedModel: 'local-model',
  setSelectedModel: noop,
  models: ['local-model'],
  apiProviders: [{ value: 'local', label: 'Local provider', models: ['local-model'] }],
  customSourcePath: project.source_path,
  batchSizeLimit: '10',
  setBatchSizeLimit: noop,
  concurrencyLimit: '1',
  setConcurrencyLimit: noop,
  rpmLimit: '40',
  setRpmLimit: noop,
  embeddedWorkshopEnabled: false,
  setEmbeddedWorkshopEnabled: noop,
  embeddedWorkshopFollowPrimary: true,
  setEmbeddedWorkshopFollowPrimary: noop,
  embeddedWorkshopProvider: 'local',
  setEmbeddedWorkshopProvider: noop,
  embeddedWorkshopModel: 'local-model',
  setEmbeddedWorkshopModel: noop,
  embeddedWorkshopBatchSize: '5',
  setEmbeddedWorkshopBatchSize: noop,
  embeddedWorkshopConcurrency: '1',
  setEmbeddedWorkshopConcurrency: noop,
  embeddedWorkshopRpm: '20',
  setEmbeddedWorkshopRpm: noop,
  showWorkshopSettings: false,
  setShowWorkshopSettings: noop,
  onBack: noop,
};

function StepFixture({ step }) {
  if (step === 'config') {
    return <ConfigStep {...sharedConfig} loading={false} runPreScan={noop} />;
  }
  if (step === 'prescan') {
    return (
      <PreScanResultsStep
        {...sharedConfig}
        scanResults={{
          total_entries: 128,
          unchanged_entries: 117,
          new_entries: 8,
          changed_entries: 3,
          file_summaries: [{
            file_path: 'localisation/english/remis_newspaper_l_english.yml',
            target_lang: 'simp_chinese',
            unchanged: 5,
            new: 8,
            changed: 3,
            dirty_entries: [],
          }],
        }}
        startTranslation={noop}
        loading={false}
        executing={false}
      />
    );
  }
  if (step === 'execution') {
    return (
      <ExecutionStep
        progress={42}
        executing
        progressInfo={{
          stage_code: 'translating_content',
          batch_idx: 2,
          total_batches: 5,
        }}
        logs={['[10:00:00] Translating simp_chinese: 2/5 batches']}
        finalSummary={null}
        logViewportRef={{ current: null }}
        logScrollRef={{ current: null }}
        onViewTask={noop}
      />
    );
  }
  return (
    <ProjectSelectStep
      projects={[project]}
      selectedProject={project}
      searchQuery=""
      setSearchQuery={noop}
      gameFilter="all"
      setGameFilter={noop}
      onSelectProject={noop}
    />
  );
}

export default function IncrementalTranslationVisualLab({ step, themeId }) {
  return (
    <main
      className={`${fixtureStyles.page} ${styles.incrementalPage}`}
      data-testid="incremental-visual-lab"
      data-step={step}
      data-theme-id={themeId}
      data-visual-ready="true"
    >
      <Container size="xl">
        <Stack gap="xs" mb="md">
          <Title order={1} className={styles.pageTitle}>
            增量翻译
          </Title>
          <Text className={fixtureStyles.subtitle}>
            真实关键子页面主题对比度与溢出夹具
          </Text>
        </Stack>
        <StepFixture step={step} />
      </Container>
    </main>
  );
}
