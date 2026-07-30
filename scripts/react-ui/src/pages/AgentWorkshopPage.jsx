import React, { useEffect, useRef } from 'react';
import {
  Title, Text, Container, Paper, Button, Group, Select, Badge, Stack, Modal, Code,
  Alert, LoadingOverlay, Box, Stepper, TextInput, SimpleGrid, Card, Progress, Accordion,
} from '@mantine/core';
import {
  IconRobot, IconCheck, IconRefresh, IconInfoCircle, IconSearch, IconWand,
  IconPlayerPlay, IconChartBar, IconSettings, IconFolderCode, IconAlertTriangle, IconEdit,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { notifications } from '@mantine/notifications';
import PerformanceControlPanel from '../components/shared/PerformanceControlPanel';
import BusyHeartbeat from '../components/shared/BusyHeartbeat';
import { useAgentWorkshopController } from '../hooks/useAgentWorkshopController';
import styles from './AgentWorkshop.module.css';
import translationStyles from './Translation.module.css';
import { buildProofreadingUrl } from '../utils/proofreadingLinks';
import { taskDetailRoute } from '../utils/taskRoutes';
import { isLocalAgentWorkshopProvider, isRepairableAgentWorkshopIssue } from '../services/agentWorkshopWorkflowService';

const AgentWorkshopPage = () => {
  const logViewportRef = useRef(null);
  const navigate = useNavigate();
  const {
    active,
    apiProviders,
    approvalOpen,
    applyCurrentFixPreview,
    archiveInfo,
    batchSizeLimit,
    closeFixModal,
    concurrencyLimit,
    confirmTutorialPrompt,
    currentIssue,
    currentRunTaskId,
    dismissTutorialPrompt,
    executeFixRun,
    executing,
    executionLogs,
    executionStats,
    filteredProjects,
    fixing,
    fixResult,
    fixedIssues,
    gameFilter,
    gameFilterOptions,
    groupedIssues,
    handleFixRequest,
    handleProjectSelect,
    handleProviderChange,
    handleScan,
    isCached,
    isModalOpen,
    issueTypeSummary,
    issues,
    latestTranslationTime,
    localizeIssueDetails,
    localizeIssueLabel,
    modelOptions,
    openFixModal,
    progress,
    projectContextLoading,
    resetFixResult,
    resetWorkflow,
    requestFixRunApproval,
    rpmLimit,
    scanLoading,
    searchQuery,
    selectedModel,
    selectedProject,
    selectedProjectId,
    selectedProvider,
    setActive,
    setBatchSizeLimit,
    setConcurrencyLimit,
    setGameFilter,
    setRpmLimit,
    setSearchQuery,
    setSelectedModel,
    showTutorialPrompt,
    setApprovalOpen,
    t,
    workflowError,
  } = useAgentWorkshopController();
  const repairableIssueCount = issues.filter(isRepairableAgentWorkshopIssue).length;

  useEffect(() => {
    if (logViewportRef.current) {
      logViewportRef.current.scrollTo({ top: logViewportRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [executionLogs]);

  const openManualProofreading = (issue) => {
    if (issue.error_code === 'validation_invalid_key_format') {
      notifications.show({
        color: 'orange',
        title: t('agent_workshop.invalid_key_manual_title'),
        message: t('agent_workshop.invalid_key_manual_help'),
      });
      return;
    }
    navigate(buildProofreadingUrl({
      projectId: selectedProjectId,
      fileId: issue.file_id,
      entryKey: issue.key,
      lineHint: issue.line_number,
    }));
  };

  return (
    <Box className={styles.container} data-remis-surface="canvas">
      <Container size="xl" py="lg">
        <Stack gap="lg">
          <Stack gap={0}>
            <Title order={2} className={styles.title}><IconRobot size={28} style={{ marginRight: 12, verticalAlign: 'middle' }} />{t('page_title_agent_workshop')}</Title>
            <Text size="sm" c="dimmed">{t('agent_workshop.description')}</Text>
          </Stack>
          {workflowError && (
            <Alert icon={<IconAlertTriangle size={16} />} color="red" radius="md">
              {String(workflowError)}
            </Alert>
          )}

          <Stepper active={active} onStepClick={setActive} allowNextStepsSelect={false} breakpoint="sm">
            <Stepper.Step label={t('agent_workshop.step_select_project')} description={t('agent_workshop.step_select_project_desc')} icon={<IconFolderCode size={18} />}>
              <Stack mt="xl">
                <Paper id="agent-workshop-project-selector" withBorder p="md" radius="md" className={translationStyles.glassCard} data-remis-surface="surface">
                  <Group grow align="flex-end">
                    <TextInput label={t('common.search')} placeholder={t('agent_workshop.project_search_placeholder')} value={searchQuery} onChange={(e) => setSearchQuery(e.currentTarget.value)} leftSection={<IconSearch size={16} />} />
                    <Select label={t('common.filter_game')} data={gameFilterOptions} value={gameFilter} onChange={(value) => setGameFilter(value || 'all')} />
                  </Group>
                </Paper>
                <SimpleGrid id="agent-workshop-project-grid" cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                  {filteredProjects.map((project) => (
                    <Card key={project.project_id} padding="lg" radius="md" withBorder onClick={() => handleProjectSelect(project.project_id)} style={{ cursor: 'pointer' }} className={selectedProjectId === project.project_id ? translationStyles.selectedCard : translationStyles.glassCard} data-remis-surface="surface">
                      <Stack gap="xs">
                        <Box><Title order={5}>{project.name}</Title><Text size="xs" c="dimmed">{project.source_path?.split(/[\\/]/).pop()}</Text></Box>
                        <Group gap="xs"><Badge color="blue" variant="light">{project.game_id}</Badge><Badge color="teal" variant="light">{project.source_language || '--'}</Badge></Group>
                        <Text size="xs" c="dimmed" lineClamp={2} className={styles.pathText}>{project.source_path}</Text>
                      </Stack>
                    </Card>
                  ))}
                </SimpleGrid>
                {!filteredProjects.length && (
                  <Alert icon={<IconInfoCircle size={16} />} color="gray" radius="md">
                    {t('agent_workshop.no_projects', { defaultValue: 'No matching projects are available.' })}
                  </Alert>
                )}
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_project_summary')} description={t('agent_workshop.step_project_summary_desc')} icon={<IconSettings size={18} />}>
              <Stack mt="xl" gap="md">
                {projectContextLoading && <Paper withBorder p="lg" radius="md" className={translationStyles.glassCard}><Text size="sm">{t('common.loading')}</Text></Paper>}
                {selectedProject && <Paper id="agent-workshop-project-summary" withBorder p="lg" radius="md" className={translationStyles.glassCard} data-remis-surface="surface"><Stack>
                  <Group justify="space-between"><Title order={4}>{selectedProject.name}</Title><Badge color="blue" variant="light">{selectedProject.game_id}</Badge></Group>
                  <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.project_source_language')}</Text><Text size="sm" fw={600}>{selectedProject.source_language || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.archived_target_languages')}</Text><Text size="sm" fw={600}>{(archiveInfo?.archived_languages || []).join(', ') || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('incremental_translation.project_game')}</Text><Text size="sm" fw={600}>{selectedProject.game_id || '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.last_translation_time')}</Text><Text size="sm" fw={600}>{latestTranslationTime ? new Date(latestTranslationTime).toLocaleString() : '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.source_entries')}</Text><Text size="sm" fw={600}>{archiveInfo?.source_entry_count ?? '--'}</Text></Card>
                    <Card withBorder p="sm" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.translation_entries')}</Text><Text size="sm" fw={600}>{archiveInfo?.total_translation_entries ?? '--'}</Text></Card>
                  </SimpleGrid>
                  <Card withBorder p="sm" radius="md" data-remis-surface="paper"><Text size="xs" c="dimmed">{t('agent_workshop.project_path')}</Text><Text size="sm" fw={500} className={styles.pathText}>{selectedProject.source_path}</Text></Card>
                  <Alert icon={<IconInfoCircle size={16} />} color="blue" radius="md"><Text size="sm">{t('agent_workshop.scan_help')}</Text></Alert>
                  <Group justify="space-between"><Button variant="light" onClick={() => setActive(0)}>{t('common.back')}</Button><Button id="agent-workshop-scan-btn" leftSection={<IconSearch size={16} />} onClick={handleScan} loading={scanLoading}>{t('agent_workshop.scan_btn')}</Button></Group>
                </Stack></Paper>}
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_scan_summary')} description={t('agent_workshop.step_scan_summary_desc')} icon={<IconChartBar size={18} />}>
              <Stack mt="xl" gap="md">
                <Paper withBorder p="lg" radius="md" className={translationStyles.glassCard} data-remis-surface="surface">
                  <SimpleGrid id="agent-workshop-fix-settings" cols={{ base: 1, sm: 2 }} spacing="md" mb="md">
                    <Select label={t('agent_workshop.provider_label')} data={apiProviders} value={selectedProvider} onChange={handleProviderChange} />
                    <Select label={t('agent_workshop.model_label')} data={modelOptions} value={selectedModel} onChange={setSelectedModel} searchable />
                  </SimpleGrid>
                  <Card withBorder p="md" radius="md" mb="lg">
                    <Text size="sm" fw={600} mb="xs">{t('translation_page.performance_settings', { defaultValue: '性能限制' })}</Text>
                    <PerformanceControlPanel
                      batchSize={batchSizeLimit}
                      onChangeBatchSize={setBatchSizeLimit}
                      concurrency={concurrencyLimit}
                      onChangeConcurrency={setConcurrencyLimit}
                      rpm={rpmLimit}
                      onChangeRpm={setRpmLimit}
                      batchSizeOpts={['1', '3', '10', '20'].map((value) => ({ value, label: value }))}
                      concurrencyOpts={['1', '2', '3', '5', '10'].map((value) => ({ value, label: value }))}
                      rpmOpts={['5', '10', '20', '30', '40', '60'].map((value) => ({ value, label: value }))}
                    />
                  </Card>
                  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="lg">
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.total_entries')}</Text><Title order={3}>{archiveInfo?.source_entry_count ?? '--'}</Title></Card>
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.issue_entries')}</Text><Title order={3} c={issues.length ? 'orange' : 'green'}>{issues.length}</Title></Card>
                    <Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.cached_state')}</Text><Title order={5}>{isCached ? t('agent_workshop.cached_label') : t('agent_workshop.scanned_label')}</Title></Card>
                  </SimpleGrid>
                  <Alert icon={<IconAlertTriangle size={16} />} color={issues.length ? 'orange' : 'green'} radius="md">
                    {issues.length
                      ? t(isLocalAgentWorkshopProvider(selectedProvider)
                        ? 'agent_workshop.start_fix_confirm_local'
                        : 'agent_workshop.start_fix_confirm_cloud')
                      : t('agent_workshop.no_errors_desc')}
                  </Alert>
                  {currentRunTaskId && (
                    <Alert icon={<IconInfoCircle size={16} />} color="blue" radius="md" mt="md">
                      <Group justify="space-between" align="center" wrap="wrap">
                        <Box>
                          <Text size="sm" fw={600}>
                            {t('agent_workshop.scan_task_recorded', {
                              defaultValue: 'This format scan is recorded in Task Center.',
                            })}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {t('task_detail.task_id')}: {currentRunTaskId}
                          </Text>
                        </Box>
                        <Button
                          variant="light"
                          size="xs"
                          onClick={() => navigate(taskDetailRoute(currentRunTaskId))}
                        >
                          {t('task_center.view_task')}
                        </Button>
                      </Group>
                    </Alert>
                  )}
                  <Group justify="flex-end" mt="md"><Button variant="light" onClick={() => setActive(1)}>{t('common.back')}</Button><Button id="agent-workshop-start-fix-btn" leftSection={<IconPlayerPlay size={18} />} onClick={requestFixRunApproval} disabled={!repairableIssueCount || !selectedProvider || !selectedModel || executing}>{t('agent_workshop.start_fix')}</Button></Group>
                  {issueTypeSummary.length > 0 && <Stack gap="xs" mt="xl"><Text size="sm" fw={600}>{t('agent_workshop.issue_type_summary')}</Text><SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>{issueTypeSummary.map((item) => <Card key={item.label} withBorder p="sm" radius="md"><Text size="xs" c="dimmed" lineClamp={2}>{localizeIssueLabel(item.label)}</Text><Text size="sm" fw={700}>{item.count}</Text></Card>)}</SimpleGrid></Stack>}
                  {groupedIssues.length > 0 && (
                    <Accordion id="agent-workshop-issue-details" variant="separated" radius="md" mt="xl">
                      <Accordion.Item value="file-details">
                        <Accordion.Control>
                          <Group justify="space-between" wrap="nowrap">
                            <Text fw={600}>{t('agent_workshop.file_issue_details')}</Text>
                            <Badge color="orange" variant="light">{groupedIssues.length}</Badge>
                          </Group>
                        </Accordion.Control>
                        <Accordion.Panel>
                          <Stack gap="sm">
                            {groupedIssues.map(([fileKey, fileIssues]) => (
                              <Accordion key={fileKey} variant="contained" radius="md">
                                <Accordion.Item value={fileKey}>
                                  <Accordion.Control>
                                    <Group justify="space-between" wrap="nowrap">
                                      <Box style={{ minWidth: 0 }}>
                                        <Text size="sm" fw={600} truncate>{fileKey}</Text>
                                        <Text size="xs" c="dimmed">{fileIssues[0]?.target_lang || '--'}</Text>
                                      </Box>
                                      <Badge color="orange" variant="light">{fileIssues.length}</Badge>
                                    </Group>
                                  </Accordion.Control>
                                  <Accordion.Panel>
                                    <Stack gap="sm">
                                      {fileIssues.map((issue, index) => {
                                        const invalidKeyIssue = issue.error_code === 'validation_invalid_key_format';
                                        return (
                                        <Paper key={`${issue.file_name}:${issue.key}:${index}`} p="sm" withBorder className={styles.issuePaper} data-remis-surface="paper">
                                          <Group justify="space-between" align="flex-start" wrap="nowrap">
                                            <Box style={{ minWidth: 0, flex: 1 }}>
                                              <Text size="sm" fw={600}>{issue.key}</Text>
                                              <Badge color="red" variant="light" mt={6} className={styles.issueBadge}>{localizeIssueLabel(issue.error_code || issue.error_type)}</Badge>
                                              <Text size="xs" c="dimmed" mt={8} className={styles.issueDetails}>{localizeIssueDetails(issue)}</Text>
                                              <Code block mt="sm" className={styles.issueText}>{issue.target_str}</Code>
                                            </Box>
                                            <Stack gap="xs">
                                              <Button
                                                size="xs"
                                                variant="light"
                                                leftSection={<IconEdit size={14} />}
                                                disabled={!issue.file_id || !issue.key}
                                                title={invalidKeyIssue ? t('agent_workshop.invalid_key_manual_help') : undefined}
                                                onClick={() => openManualProofreading(issue)}
                                                style={{ whiteSpace: 'nowrap' }}
                                              >
                                                {t('proofreading.open_entry', { defaultValue: 'Manual proofreading' })}
                                              </Button>
                                              <Button
                                                size="xs" variant="light" leftSection={<IconWand size={14} />} disabled={invalidKeyIssue}
                                                title={invalidKeyIssue ? t('agent_workshop.invalid_key_manual_help') : undefined}
                                                onClick={() => openFixModal(issue)} style={{ whiteSpace: 'nowrap' }}
                                              >
                                                {t('agent_workshop.fix_btn')}
                                              </Button>
                                            </Stack>
                                          </Group>
                                        </Paper>
                                        );
                                      })}
                                    </Stack>
                                  </Accordion.Panel>
                                </Accordion.Item>
                              </Accordion>
                            ))}
                          </Stack>
                        </Accordion.Panel>
                      </Accordion.Item>
                    </Accordion>
                  )}
                </Paper>
              </Stack>
            </Stepper.Step>

            <Stepper.Step label={t('agent_workshop.step_execution')} description={t('agent_workshop.step_execution_desc')} icon={<IconRobot size={18} />}>
              <Stack mt="xl"><Paper id="agent-workshop-execution-panel" withBorder p="xl" radius="md" className={translationStyles.glassCard} data-remis-surface="surface">
                <Title order={4} mb="md">{t('agent_workshop.execution_title')}</Title>
                {currentRunTaskId && (
                  <Alert icon={<IconInfoCircle size={16} />} color="blue" radius="md" mb="md">
                    <Group justify="space-between" align="center">
                      <Box>
                        <Text size="sm" fw={600}>
                          {executing
                            ? t('agent_workshop.task_accepted', { defaultValue: 'Repair task accepted and running in the background.' })
                            : t('agent_workshop.task_result_ready', { defaultValue: 'This run is recorded in the Task Center.' })}
                        </Text>
                        <Text size="xs" c="dimmed">{t('task_detail.task_id')}: {currentRunTaskId}</Text>
                      </Box>
                      <Button variant="light" size="xs" onClick={() => navigate(taskDetailRoute(currentRunTaskId))}>
                        {t('task_center.view_task')}
                      </Button>
                    </Group>
                  </Alert>
                )}
                <Progress value={progress} label={progress > 0 ? `${progress}%` : ''} size="xl" radius="xl" animated={executing} mb="sm" />
                {executing && (
                  <BusyHeartbeat
                    active
                    compact
                    title={t('agent_workshop.execution_in_progress')}
                    description={executionStats ? `${executionStats.completed} / ${executionStats.total}` : t('agent_workshop.execution_pending')}
                    color="teal"
                  />
                )}
                <Group justify="space-between" mt={executing ? 'md' : 0} mb="xl"><Box><Text size="sm" fw={600}>{executing ? t('agent_workshop.execution_in_progress') : t('agent_workshop.execution_completed')}</Text><Text size="xs" c="dimmed">{executionStats ? `${executionStats.completed} / ${executionStats.total}` : t('agent_workshop.execution_pending')}</Text></Box><Text size="xs" fw={700} c="blue">{progress}%</Text></Group>
                <Box ref={logViewportRef} className={translationStyles.logScrollBox}>{executionLogs.map((log, index) => <Text key={`${log}-${index}`} size="xs" style={{ fontFamily: 'monospace' }} mb={2}>{log}</Text>)}</Box>
              {executionStats && !executing && <Stack mt="xl"><SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md"><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.fixed_count')}</Text><Title order={3} c="green">{executionStats.successCount}</Title></Card><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.failed_count')}</Text><Title order={3} c="orange">{executionStats.failedCount}</Title></Card><Card withBorder p="md" radius="md"><Text size="xs" c="dimmed">{t('agent_workshop.duration')}</Text><Title order={5}>{`${(executionStats.durationMs / 1000).toFixed(1)} s`}</Title></Card></SimpleGrid>
                {fixedIssues.length > 0 && (
                  <Accordion id="agent-workshop-diff-preview" variant="separated" radius="md">
                    <Accordion.Item value="diff-preview">
                      <Accordion.Control>{t('agent_workshop.diff_preview')}</Accordion.Control>
                      <Accordion.Panel>
                        <Stack gap="md">
                          {fixedIssues.map((issue, index) => (
                            <Paper key={`${issue.file_name}:${issue.key}:${index}`} withBorder p="md" radius="md">
                              <Stack gap="xs">
                                <Group justify="space-between" wrap="nowrap">
                                  <Box style={{ minWidth: 0 }}>
                                    <Text size="sm" fw={700}>{issue.key}</Text>
                                    <Text size="xs" c="dimmed" truncate>{issue.file_name}</Text>
                                  </Box>
                                  <Badge color="green" variant="light">{localizeIssueLabel(issue.error_code || issue.error_type)}</Badge>
                                </Group>
                                <Text size="xs" c="dimmed">{localizeIssueDetails(issue)}</Text>
                                <Text size="xs" fw={700}>{t('agent_workshop.before_fix')}</Text>
                                <Code block>{issue.target_str}</Code>
                                <Text size="xs" fw={700}>{t('agent_workshop.after_fix')}</Text>
                                <Code block>{issue.suggested_fix}</Code>
                                {issue.report_path && <Text size="xs" c="dimmed">{t('agent_workshop.report_path')}: {issue.report_path}</Text>}
                              </Stack>
                            </Paper>
                          ))}
                        </Stack>
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                )}
                <Group><Button onClick={resetWorkflow}>{t('common.finish')}</Button></Group></Stack>}
              </Paper></Stack>
            </Stepper.Step>
          </Stepper>
        </Stack>

        <Modal
          opened={approvalOpen}
          onClose={() => setApprovalOpen(false)}
          title={t('agent_workshop.start_fix')}
          centered
          radius="md"
          classNames={{
            content: styles.approvalModalContent,
            header: styles.approvalModalHeader,
            title: styles.approvalModalTitle,
            body: styles.approvalModalBody,
            close: styles.approvalModalClose,
          }}
        >
          <Stack data-remis-surface="paper">
            <Alert icon={<IconAlertTriangle size={16} />} color="orange" radius="md" className={styles.approvalWarning}>
              {t(isLocalAgentWorkshopProvider(selectedProvider)
                ? 'agent_workshop.start_fix_confirm_local'
                : 'agent_workshop.start_fix_confirm_cloud')}
            </Alert>
            <SimpleGrid cols={2} spacing="xs">
              <Text size="sm" c="dimmed">{t('agent_workshop.issue_entries')}</Text>
              <Text size="sm" fw={600}>{repairableIssueCount}</Text>
              <Text size="sm" c="dimmed">{t('agent_workshop.provider_label')}</Text>
              <Text size="sm" fw={600}>{selectedProvider}</Text>
              <Text size="sm" c="dimmed">{t('agent_workshop.model_label')}</Text>
              <Text size="sm" fw={600}>{selectedModel}</Text>
            </SimpleGrid>
            <Text size="xs" c="dimmed">
              {t('agent_workshop.approval_scope_notice', {
                defaultValue: 'Approval applies only to this project, issue count, provider, and model. The run may write repairs to project translation files.',
              })}
            </Text>
            <Group justify="flex-end">
              <Button variant="subtle" color="gray" onClick={() => setApprovalOpen(false)} data-remis-action="secondary" className={styles.approvalSecondary}>
                {t('cancel')}
              </Button>
              <Button color="orange" leftSection={<IconPlayerPlay size={16} />} onClick={executeFixRun} data-remis-action="primary" disabled={executing}>
                {t('agent_workshop.start_fix')}
              </Button>
            </Group>
          </Stack>
        </Modal>

        <Modal
          opened={isModalOpen}
          onClose={closeFixModal}
          title={<Group gap="xs"><IconRobot size={20} /><Text fw={600}>{t('agent_workshop.modal_title')}</Text></Group>}
          size="lg"
          classNames={{
            content: styles.issueFixModalContent,
            header: styles.issueFixModalHeader,
            title: styles.issueFixModalTitle,
            body: styles.issueFixModalBody,
            close: styles.issueFixModalClose,
          }}
        >
          <Box style={{ position: 'relative' }} data-remis-surface="paper">
            <LoadingOverlay visible={fixing} overlayBlur={2} />
            <Stack gap="md">
              <Paper p="sm" withBorder className={styles.issueFixPanel}>
                <Text size="xs" fw={700} c="dimmed" tt="uppercase">{t('agent_workshop.modal_source_context')}</Text>
                <Code block className={styles.issueFixCode}>{currentIssue?.source_str || t('agent_workshop.no_source_context')}</Code>
              </Paper>
              <Paper p="sm" withBorder className={styles.issueFixPanel}>
                <Text size="xs" fw={700} c="red" tt="uppercase">{t('agent_workshop.modal_error_detected')}</Text>
                <Code block className={styles.issueFixErrorCode}>{currentIssue?.target_str}</Code>
                <Text size="xs" mt={6}>{localizeIssueDetails(currentIssue)}</Text>
              </Paper>
              {!fixResult && (
                <>
                  <Box>
                    <Text size="sm" fw={700}>{t('agent_workshop.repair_model_heading')}</Text>
                    <Text size="xs" c="dimmed" mb="xs">{t('agent_workshop.repair_model_help')}</Text>
                    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                      <Select
                        label={t('agent_workshop.provider_label')}
                        data={apiProviders}
                        value={selectedProvider}
                        onChange={handleProviderChange}
                      />
                      <Select
                        label={t('agent_workshop.model_label')}
                        data={modelOptions}
                        value={selectedModel}
                        onChange={setSelectedModel}
                        searchable
                      />
                    </SimpleGrid>
                  </Box>
                  <Alert icon={<IconAlertTriangle size={16} />} color="orange" radius="md" className={styles.approvalWarning}>
                    {t(isLocalAgentWorkshopProvider(selectedProvider)
                      ? 'agent_workshop.single_fix_confirm_local'
                      : 'agent_workshop.single_fix_confirm_cloud')}
                  </Alert>
                </>
              )}
              {!fixResult && (
                <Button
                  fullWidth
                  onClick={handleFixRequest}
                  disabled={fixing || !selectedProvider || !selectedModel}
                  data-remis-action="paper-primary"
                >
                  {selectedProvider && selectedModel ? t('agent_workshop.fix_btn') : t('agent_workshop.select_model_hint')}
                </Button>
              )}
              {fixResult && (
                <Stack gap="md">
                  <Alert icon={<IconInfoCircle size={16} />} title={t('agent_workshop.modal_analysis')} color="indigo" variant="light" className={styles.issueFixResult}>
                    <Text size="sm">{fixResult.reflection}</Text>
                    {fixResult.report_path && <Text size="xs" mt={8} c="dimmed">{t('agent_workshop.report_path')}: {fixResult.report_path}</Text>}
                  </Alert>
                  <Paper p="sm" withBorder className={styles.issueFixPanel}>
                    <Text size="xs" fw={700} tt="uppercase">{t('agent_workshop.modal_suggestion')}</Text>
                    <Code block className={styles.issueFixCode}>{fixResult.suggested_fix}</Code>
                    {fixResult.parity_message && <Text size="xs" mt={6}><IconCheck size={12} /> {fixResult.parity_message}</Text>}
                  </Paper>
                  <Group grow mt="sm">
                    <Button variant="subtle" onClick={resetFixResult} data-remis-action="paper-secondary">{t('agent_workshop.regenerate')}</Button>
                    <Button onClick={applyCurrentFixPreview} data-remis-action="paper-primary">{t('agent_workshop.apply_fix')}</Button>
                  </Group>
                </Stack>
              )}
            </Stack>
          </Box>
        </Modal>

        <Modal
          opened={showTutorialPrompt}
          onClose={dismissTutorialPrompt}
          title={t('tutorial.auto_start_prompt.title')}
          centered
          radius="md"
        >
          <Stack>
            <Text size="sm">{t('tutorial.auto_start_prompt.message')}</Text>
            <Group justify="flex-end" mt="md">
              <Button
                variant="subtle"
                color="gray"
                onClick={dismissTutorialPrompt}
              >
                {t('tutorial.auto_start_prompt.cancel')}
              </Button>
              <Button
                color="blue"
                onClick={confirmTutorialPrompt}
              >
                {t('tutorial.auto_start_prompt.confirm')}
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Container>
    </Box>
  );
};

export default AgentWorkshopPage;
