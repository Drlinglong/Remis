import React from 'react';
import { Button, Card, Grid, Group, Menu, Paper, Progress, Stack, Text, Title } from '@mantine/core';
import {
    IconArchive,
    IconAlertTriangle,
    IconChecklist,
    IconDatabaseCog,
    IconDotsVertical,
    IconPlayerPlay,
    IconRefresh,
    IconRestore,
    IconRocket,
    IconSettings,
    IconTrash,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { useDeployActions } from '../../hooks/useDeployActions';
import styles from '../../pages/ProjectManagement.module.css';
import { getProjectPrimaryAction } from '../../utils/projectPrimaryAction';
import { DeployModals } from '../deploy/DeployModals';

const ProjectHeader = ({
    projectDetails,
    handleStatusChange,
    onDeleteForever,
    onManageProject,
    onRefresh,
    onRepairMetadata,
    repairingMetadata,
}) => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const overview = projectDetails.overview || {};
    const translated = Number(overview.translated || 0);
    const primaryAction = getProjectPrimaryAction(projectDetails);
    const archiveSummary = projectDetails?.archive_summary || null;
    const latestArchiveTime = archiveSummary?.last_upload_at || archiveSummary?.created_at || null;

    const deployActions = useDeployActions({
        getOutputFolderName: () => {
            const outputDir = Array.isArray(projectDetails?.translation_dirs) && projectDetails.translation_dirs.length > 0
                ? projectDetails.translation_dirs[0]
                : null;
            return outputDir ? outputDir.split(/[\\/]/).pop() : projectDetails.name;
        },
        projectId: projectDetails?.project_id,
        gameId: projectDetails?.game_id,
    });
    const { handleOpenDeployModal, handleOpenCleanModal } = deployActions;

    const runPrimaryAction = () => {
        if (primaryAction === 'restore') return handleStatusChange('active');
        if (primaryAction === 'fix_format') return navigate('/agent-workshop', { state: { projectId: projectDetails.project_id } });
        if (primaryAction === 'proofread') return navigate(`/proofreading?projectId=${projectDetails.project_id}`);
        if (primaryAction === 'deploy') return handleOpenDeployModal();
        return navigate(`/translation?projectId=${projectDetails.project_id}`);
    };

    const primaryLabels = {
        restore: t('project_management.restore_project'),
        fix_format: t('project_management.primary_fix_format'),
        proofread: t('project_management.primary_continue_proofreading'),
        translate: translated > 0 ? t('project_management.primary_continue_translation') : t('button_start_translation'),
        deploy: t('button_auto_deploy'),
    };
    const PrimaryIcon = primaryAction === 'restore'
        ? IconRestore
        : primaryAction === 'fix_format'
            ? IconAlertTriangle
        : primaryAction === 'proofread'
            ? IconChecklist
            : primaryAction === 'deploy'
                ? IconRocket
                : IconPlayerPlay;

    return (
        <Paper data-remis-surface="surface" withBorder p={{ base: 'sm', md: 'md' }} radius="md" className={`${styles.glassCard} ${styles.surfacePanel}`} mb="md">
            <Group justify="space-between" align="flex-start" mb="md" gap="sm">
                <div>
                    <Text size="xs" fw={700} c="dimmed" tt="uppercase">{t('project_management.current_state')}</Text>
                    <Title order={3}>{primaryLabels[primaryAction]}</Title>
                    <Text size="sm" c="dimmed">{t(`project_management.primary_hint.${primaryAction}`)}</Text>
                </div>
                <Group gap="xs">
                    <Button leftSection={<PrimaryIcon size={18} />} onClick={runPrimaryAction}>
                        {primaryLabels[primaryAction]}
                    </Button>
                    <Menu position="bottom-end" withinPortal shadow="md" transitionProps={{ duration: 0 }}>
                        <Menu.Target>
                            <Button variant="default" px="xs" aria-label={t('project_management.project_menu')}>
                                <IconDotsVertical size={18} />
                            </Button>
                        </Menu.Target>
                        <Menu.Dropdown data-remis-surface="elevated" className={styles.projectMenuDropdown}>
                            <Menu.Label>{t('project_management.project_menu')}</Menu.Label>
                            {projectDetails.status === 'active' && (
                                <>
                                    <Menu.Item leftSection={<IconSettings size={16} />} onClick={onManageProject}>
                                        {t('project_management.manage_project')}
                                    </Menu.Item>
                                    <Menu.Item leftSection={<IconRefresh size={16} />} onClick={onRefresh}>
                                        {t('project_management.refresh_files')}
                                    </Menu.Item>
                                    <Menu.Item leftSection={<IconDatabaseCog size={16} />} onClick={onRepairMetadata} disabled={repairingMetadata}>
                                        {t('project_management.repair_metadata', 'Repair Metadata')}
                                    </Menu.Item>
                                    <Menu.Item leftSection={<IconRocket size={16} />} onClick={handleOpenDeployModal}>
                                        {t('button_auto_deploy')}
                                    </Menu.Item>
                                    <Menu.Divider />
                                    <Menu.Item color="orange" leftSection={<IconArchive size={16} />} onClick={() => handleStatusChange('archived')}>
                                        {t('project_management.archive_project')}
                                    </Menu.Item>
                                    <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={handleOpenCleanModal}>
                                        {t('button_clean_fake_loc')}
                                    </Menu.Item>
                                    <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={onDeleteForever}>
                                        {t('project_management.delete_project')}
                                    </Menu.Item>
                                </>
                            )}
                            {projectDetails.status === 'archived' && (
                                <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={() => handleStatusChange('deleted')}>
                                    {t('project_management.delete_project')}
                                </Menu.Item>
                            )}
                            {projectDetails.status === 'deleted' && (
                                <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={onDeleteForever}>
                                    {t('project_management.delete_forever')}
                                </Menu.Item>
                            )}
                        </Menu.Dropdown>
                    </Menu>
                </Group>
            </Group>

            <Grid gutter="sm" align="stretch">
                <Grid.Col span={{ base: 12, md: 6 }}>
                    <Card data-remis-surface="surface" withBorder h="100%" className={styles.surfaceInset}>
                        <Group justify="space-between"><Text fw={700}>{t('project_management.overview.translated')}</Text><Text fw={700}>{translated}%</Text></Group>
                        <Progress value={translated} mt="sm" size="lg" radius="xl" />
                        <Group justify="space-between" mt="sm">
                            <Text size="sm" c="dimmed">{t('project_management.overview.to_be_proofread')}</Text>
                            <Text size="sm" fw={600}>{overview.toBeProofread || 0}%</Text>
                        </Group>
                    </Card>
                </Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3, md: 1.5 }}><Card data-remis-surface="surface" withBorder className={styles.surfaceInset} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_files')}</Text><Title order={3}>{overview.totalFiles || 0}</Title></Card></Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3, md: 1.5 }}><Card data-remis-surface="surface" withBorder className={styles.surfaceInset} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_lines')}</Text><Title order={3}>{overview.totalLines || 0}</Title></Card></Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                    <Card data-remis-surface="surface" withBorder className={styles.surfaceInset} h="100%">
                        <Stack gap={4}>
                            <Text size="xs" c="dimmed">{t('incremental_translation.archived_target_languages')}</Text>
                            <Text size="sm" fw={600}>{Array.isArray(projectDetails.archived_languages) && projectDetails.archived_languages.length > 0 ? projectDetails.archived_languages.join(', ') : t('incremental_translation.none_archived')}</Text>
                            <Text size="xs" c="dimmed" mt="xs">{t('project_history.last_archive_time', 'Last Upload / Build')}</Text>
                            <Text size="xs">{latestArchiveTime ? new Date(latestArchiveTime).toLocaleString() : t('project_history.no_archive_data', 'No archive data')}</Text>
                        </Stack>
                    </Card>
                </Grid.Col>
            </Grid>
            <DeployModals deployActions={deployActions} />
        </Paper>
    );
};

export default ProjectHeader;
