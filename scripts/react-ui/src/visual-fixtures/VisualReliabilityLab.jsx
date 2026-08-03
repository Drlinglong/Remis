import React from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCheck,
  IconDatabase,
  IconFileDescription,
  IconGavel,
  IconX,
} from '@tabler/icons-react';

import {
  ArchiveSummary,
  ReleaseMetadata,
} from '../components/neologism/PublishedArchiveContent';
import RemoveModArchiveControl from '../components/neologism/RemoveModArchiveControl';
import styles from './VisualReliabilityLab.module.css';

const longProjectName = 'Project Remis — Demo Mod — Stellaris — 超长项目身份验证';
const longWindowsPath = String.raw`C:\Users\Drlin\AppData\Roaming\RemisModFactoryDev\demo\localisation\simp_chinese\remis_demo_events_l_english.yml`;

function SurfaceSample({ surface, title, children, testId }) {
  return (
    <Paper
      className={styles.surfaceSample}
      data-remis-surface={surface}
      data-testid={testId}
      radius="md"
      p="md"
      withBorder
    >
      <Text className={styles.eyebrow}>{surface}</Text>
      <Title order={3} className={styles.sectionTitle}>{title}</Title>
      {children}
    </Paper>
  );
}

function ProjectGlossaryContrastFixture({ themeId }) {
  return (
    <Box
      className={styles.page}
      data-remis-surface="canvas"
      data-testid="project-glossary-contrast-fixture"
      data-visual-ready="true"
    >
      <Paper
        className={styles.surfaceSample}
        data-remis-surface="paper"
        p="lg"
        radius="md"
        withBorder
      >
        <Stack gap="sm">
          <Group justify="space-between" align="flex-start">
            <Box>
              <Title order={3} data-testid="project-glossary-title">
                项目词典
              </Title>
              <Text c="dimmed" size="sm" data-testid="project-glossary-description">
                新词挖掘机自动生成的 Mod 词典会与当前 Mod 项目绑定。
              </Text>
            </Box>
            <Badge
              color="teal"
              variant="light"
              leftSection={<IconDatabase size={12} />}
              data-testid="project-glossary-badge"
            >
              蕾姆丝计划 - 演示MOD - 维多利亚3
            </Badge>
          </Group>
          <Alert icon={<IconAlertTriangle size={18} />} color="blue" variant="light">
            <Text data-testid="project-glossary-alert">
              当新词挖掘开始时，Remis 会自动创建并绑定项目词典。
            </Text>
          </Alert>
          <Text size="xs" c="dimmed">{themeId}</Text>
        </Stack>
      </Paper>
    </Box>
  );
}

const archiveTranslations = {
  'mod_archive.release.read_only': '只读发布版本，人工修订将写入新草稿。',
  'mod_archive.release.start_draft': '从此版本开始草稿',
  'mod_archive.release.refresh': '刷新',
  'mod_archive.release.created_at': '发布时间',
  'mod_archive.release.provider': '供应商',
  'mod_archive.release.model': '模型',
  'mod_archive.release.metadata_title': '版本元数据',
  'mod_archive.release.release_id': '版本 ID',
  'mod_archive.release.project_id': '项目 ID',
  'mod_archive.release.analysis_scope': '范围',
  'mod_archive.release.analysis_scopes.narrative_context': '完整档案分析',
  'mod_archive.release.schema_version': '档案格式版本',
  'mod_archive.release.prompt_example': '分析提示词示例',
  'mod_archive.release.prompt_example_unavailable': '此旧版本没有可用的提示词示例。',
  'mod_archive.release.source_snapshot': '源快照',
  'mod_archive.release.upstream_version': '上游版本',
  'mod_archive.release.parent_release': '父版本',
  'mod_archive.release.not_available': '未记录',
  'mod_archive.release.summary_title': '有效档案摘要',
  'mod_archive.release.summary_desc': '这些值合并了生成摘要，以及版本中保留的人工覆盖值。',
  'mod_archive.release.project_summary': '项目摘要',
  'mod_archive.release.event_summary': '事件摘要',
  'mod_archive.release.entity_summary': '实体摘要',
  'mod_archive.release.no_project_summary': '暂无项目摘要。',
  'mod_archive.release.no_event_summary': '暂无事件摘要。',
  'mod_archive.release.no_entity_summary': '暂无实体摘要。',
  'mod_archive.release.override_badge': '人工覆盖',
  'mod_archive.release.effective_override': '有效覆盖值',
  'mod_archive.release.term_status.approved': '项目词典',
  'mod_archive.release.term_status.suggested': '待审建议',
  'mod_archive.release.provenance.text_inferred': '文本推断',
  'mod_archive.release.provenance.script_derived': '脚本结构推导',
  'mod_archive.release.contribution_type.fact': '事实',
  'mod_archive.release.contribution_type.event': '事件',
  'mod_archive.release.traceability_title': '源文件来源依据与可追溯性',
  'mod_archive.release.traceability_desc': '按项目、事件与实体检查每个展示对象的来源证据。',
  'mod_archive.release.evidence_membership_count': '摘要证据：{{count}}',
  'mod_archive.release.delivery_membership_count': '翻译覆盖：{{count}}',
  'mod_archive.release.traceability_empty': '此版本没有可用的追踪记录。',
  'mod_archive.release.removal.open': '移除项目档案',
  'mod_archive.release.removal.title': '移除项目档案',
  'mod_archive.release.removal.warning_title': '这会移除所有已生成的档案数据',
  'mod_archive.release.removal.warning_desc': '该项目的发布版本、草稿、证据聚合和可续传分析检查点都会被永久移除。',
  'mod_archive.release.removal.confirm': '确定移除“{{project}}”的完整档案吗？之后可以重新运行完整档案分析来重建。',
  'mod_archive.release.removal.preserved': 'Mod 源文件、项目、项目词典和新词候选会保留。',
  'mod_archive.release.removal.cancel': '保留档案',
  'mod_archive.release.removal.confirm_action': '确认移除档案',
  'mod_archive.release.removal.error': '无法移除项目档案。',
};

const archiveT = (key, options = {}) => String(archiveTranslations[key] || key).replace(
  /\{\{(\w+)\}\}/g,
  (_match, name) => String(options[name] ?? `{{${name}}}`),
);

function PublishedArchiveVisualFixture() {
  const entries = [
    {
      key: 'project:summary', kind: 'project', label: 'summary',
      value: { summary: '一个围绕瑞米斯女皇与银河共和国危机展开的叙事型模组。' },
    },
    {
      key: 'event:remis_crisis', kind: 'event', label: 'remis_crisis',
      value: { summary: '瑞米斯夺取最高权力，旧共和国在忠诚与反抗之间分裂。' },
    },
    {
      key: 'entity:empress remis', kind: 'entity', label: 'empress remis',
      termReference: { translation: '瑞米斯女皇', status: 'suggested' },
      value: { summary: '原为最高议长，后通过武力夺权并重组银河共和国。' },
    },
    {
      key: 'entity:galactic republic', kind: 'entity', label: 'galactic republic',
      termReference: { translation: '银河共和国', status: 'approved' },
      value: { summary: '横跨多个星区的政体，也是危机事件链的主要舞台。' },
    },
    {
      key: 'entity:watch of quiet stars', kind: 'entity', label: 'watch of quiet stars',
      termReference: { translation: '寂星守望者', status: 'suggested' },
      value: { summary: '秘密监视政局变化并保存旧共和国记录的组织。' },
    },
    {
      key: 'entity:the exceptionally long unbroken localization identifier',
      kind: 'entity',
      label: 'the exceptionally long unbroken localization identifier',
      value: { summary: '用于验证长名称在并列实体卡片中仍能换行且不产生横向滚动。' },
    },
  ];
  const rows = entries.flatMap((entry, index) => ([{
    aggregateKey: entry.key,
    aggregateType: entry.kind,
    contributionType: entry.kind === 'event' ? 'event' : 'fact',
    provenance: index % 2 === 0 ? 'text_inferred' : 'script_derived',
    sourceRef: `localisation/english/remis_crisis_l_english.yml::${index + 1}:${entry.label}`,
    sourceContent: `Source evidence for ${entry.label}.`,
    deliveryMembershipCount: entry.kind === 'event' ? 42 : 0,
  }]));
  return (
    <Box
      className={styles.page}
      data-remis-surface="canvas"
      data-testid="published-archive-visual-fixture"
      data-visual-ready="true"
    >
      <Group justify="flex-end" mb="md">
        <RemoveModArchiveControl
          projectId="project-remis-demo"
          projectName={longProjectName}
          onRemoved={() => {}}
          t={archiveT}
        />
      </Group>
      <ReleaseMetadata
        release={{
          release_id: 'release-2026-08-03',
          project_id: 'project-remis-demo',
          metadata: {
            created_at: '2026-08-03T11:25:00',
            provider_id: 'openrouter',
            model_id: 'openai/gpt-5.6-luna',
            source_snapshot_hash: 'a5b118aa79b335e36bb456a19f4e8300d484b2ca0d8d1288ef6136aa51c737ba',
            schema_version: 'context-v2',
            prompt_version: 'context-synthesis-v3',
            analysis_config: { description_language: 'zh-CN', temperature: 0 },
            prompt_example: 'System message:\nSummarize source-grounded localization context in Simplified Chinese.\n\nUser message:\nExample source evidence.',
            upstream_version: '3.1.1',
          },
        }}
        selectedProject="project-remis-demo"
        scope="narrative_context"
        draftState={{ phase: 'idle', startDraft: () => {} }}
        refresh={() => {}}
        t={archiveT}
      />
      <ArchiveSummary
        entries={entries}
        counts={{ project: 1, event: 1, entity: 4 }}
        rows={rows}
        traceabilityState="ready"
        traceabilityError=""
        loadTraceability={() => {}}
        t={archiveT}
      />
    </Box>
  );
}

export default function VisualReliabilityLab({ themeId, contract }) {
  if (contract === 'project-glossary') {
    return <ProjectGlossaryContrastFixture themeId={themeId} />;
  }
  if (contract === 'published-archive') {
    return <PublishedArchiveVisualFixture />;
  }

  return (
    <Box
      className={styles.page}
      data-remis-surface="canvas"
      data-testid="visual-reliability-lab"
      data-visual-ready="true"
    >
      <header className={styles.header}>
        <Box>
          <Text className={styles.eyebrow}>Remis UI contract fixture</Text>
          <Title order={1}>前端视觉可靠性实验室</Title>
          <Text className={styles.canvasMuted}>
            固定内容用于检测主题层级、长文本、交互状态和溢出回归。
          </Text>
        </Box>
        <Badge size="lg" variant="outline">{themeId}</Badge>
      </header>

      <Paper
        className={styles.toolbar}
        data-remis-surface="surface"
        p="md"
        radius="md"
        withBorder
      >
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <Select
            className={styles.projectField}
            classNames={{
              label: styles.surfaceLabel,
            }}
            label="当前项目"
            value="demo"
            data={[{ value: 'demo', label: longProjectName }]}
            readOnly
          />
          <Group gap="sm">
            <Badge variant="light">21 个待审术语</Badge>
            <Button data-remis-action="primary" leftSection={<IconGavel size={16} />}>
              查看当前案件
            </Button>
          </Group>
        </Group>
      </Paper>

      <main className={styles.grid}>
        <SurfaceSample
          surface="surface"
          title="当前任务"
          testId="surface-contract-sample"
        >
          <Stack gap="sm">
            <Group justify="space-between" align="flex-start">
              <Box className={styles.minWidthZero}>
                <Text fw={700}>增量翻译等待校对</Text>
                <Text className={styles.surfaceMuted}>
                  已扫描 12 个文件，发现 11 项变更。任务状态和下一步保持清晰。
                </Text>
              </Box>
              <Badge color="orange" variant="light">需要处理</Badge>
            </Group>
            <Group gap="sm">
              <Button data-remis-action="primary" leftSection={<IconCheck size={16} />}>
                继续校对
              </Button>
              <Button data-remis-action="secondary" variant="default">
                查看任务
              </Button>
            </Group>
          </Stack>
        </SurfaceSample>

        <SurfaceSample
          surface="paper"
          title="来源证据"
          testId="paper-contract-sample"
        >
          <Stack gap="sm">
            <Group gap="sm" wrap="nowrap" align="flex-start">
              <ThemeIcon variant="light">
                <IconFileDescription size={18} />
              </ThemeIcon>
              <Box className={styles.minWidthZero}>
                <Text fw={700}>Silence in the Halls / 殿堂沉寂</Text>
                <Text
                  className={styles.longPath}
                  data-testid="long-windows-path"
                  title={longWindowsPath}
                >
                  {longWindowsPath}
                </Text>
              </Box>
            </Group>
            <Text className={styles.paperMuted}>
              次要文字仍需清晰可读，完整路径必须在边框内自动换行。
            </Text>
          </Stack>
        </SurfaceSample>

        <SurfaceSample
          surface="elevated"
          title="临时浮层"
          testId="elevated-contract-sample"
        >
          <Stack gap="sm">
            <Text className={styles.elevatedText}>
              部署和覆盖操作必须先呈现预览及影响范围。
            </Text>
            <Alert
              icon={<IconAlertTriangle size={18} />}
              title="尚未执行危险操作"
              color="yellow"
            >
              此夹具只验证视觉状态，不写入项目、数据库或部署目录。
            </Alert>
          </Stack>
        </SurfaceSample>
      </main>

      <section className={styles.lowerGrid}>
        <Paper
          className={styles.decisionPanel}
          data-remis-surface="surface"
          p="md"
          radius="md"
          withBorder
        >
          <Text className={styles.eyebrow}>decision surface</Text>
          <Title order={2}>术语判决</Title>
          <Stack gap="sm">
            <Select
              classNames={{
                label: styles.surfaceLabel,
                description: styles.surfaceDescription,
              }}
              label="如何处理这个术语冲突？"
              description="选择沿用已有译法，或为当前项目建立明确覆盖。"
              value="reuse"
              data={[{ value: 'reuse', label: '沿用现有词典译法' }]}
              readOnly
            />
            <TextInput
              classNames={{
                label: styles.surfaceLabel,
                description: styles.surfaceDescription,
              }}
              label="最终翻译"
              description="在批准前审查并编辑建议的翻译。"
              value="新秩序的黎明"
              readOnly
            />
            <Group justify="flex-end" gap="sm">
              <Button
                data-remis-action="danger-secondary"
                variant="default"
                leftSection={<IconX size={16} />}
              >
                驳回 / 忽略
              </Button>
              <Button
                data-remis-action="primary"
                leftSection={<IconGavel size={16} />}
              >
                批准术语
              </Button>
            </Group>
          </Stack>
        </Paper>

        <Paper
          className={styles.scrollPanel}
          data-remis-surface="surface"
          p="md"
          radius="md"
          withBorder
        >
          <Group justify="space-between">
            <Box>
              <Text className={styles.eyebrow}>single scroll owner</Text>
              <Title order={2}>案卷列表</Title>
            </Box>
            <Badge variant="light">6</Badge>
          </Group>
          <div className={styles.scrollOwner} data-testid="docket-scroll-owner">
            {[
              'Central Palace / 中央皇宫',
              'Sol-Lance / 索尔光矛',
              'Empress Remis / 蕾姆丝女皇',
              'Eternal Vigilance / 永恒警惕',
              'Argentum Standard / 银本位',
              'Absolute Sublimation / 绝对升华',
            ].map((item) => (
              <Paper
                key={item}
                data-remis-surface="paper"
                className={styles.docketItem}
                p="sm"
                radius="sm"
                withBorder
              >
                <Text fw={700}>{item}</Text>
                <Text className={styles.paperMuted}>来源上下文和处理状态保持可读</Text>
              </Paper>
            ))}
          </div>
        </Paper>
      </section>

      <footer className={styles.footer} data-remis-surface="surface">
        <Group gap="xs">
          <IconDatabase size={16} />
          <Text size="sm">确定性夹具，不连接后端、不调用模型、不执行写入。</Text>
        </Group>
        <Button disabled>禁用状态</Button>
      </footer>
    </Box>
  );
}
