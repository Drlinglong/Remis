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

export default function VisualReliabilityLab({ themeId }) {
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
