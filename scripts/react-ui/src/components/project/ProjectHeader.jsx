import React from 'react';
import { Button, Card, Group, Menu, Paper, Progress, Text, Title } from '@mantine/core';
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
import { useNavigate } from 'react-router';

import { useDeployActions } from '../../hooks/useDeployActions';
import surfaceStyles from './ProjectDetailSurfaces.module.css';
import headerStyles from './ProjectHeader.module.css';
import { getProjectPrimaryAction } from '../../utils/projectPrimaryAction';
import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../utils/localizedDateTime';
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
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const overview = projectDetails.overview || {};
    const translated = Number(overview.translated || 0);
    const validationIssues = Number(projectDetails.validation?.issues_count || 0);
    const releaseReady = Boolean(projectDetails.has_available_translation) && validationIssues === 0;
    const primaryAction = getProjectPrimaryAction(projectDetails);
    const canDeployAvailableTranslation = projectDetails.status === 'active'
        && Boolean(projectDetails.has_available_translation)
        && validationIssues === 0;
    const showDirectDeployAlongsidePrimary = canDeployAvailableTranslation
        && primaryAction !== 'deploy';
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
        <Paper data-remis-surface="surface" withBorder p={{ base: 'sm', md: 'md' }} radius="md" className={`${surfaceStyles.glassCard} ${surfaceStyles.surfacePanel} ${headerStyles.header}`} mb="md">
            <Group justify="space-between" align="flex-start" mb="md" gap="sm">
                <div>
                    <Text size="xs" fw={700} c="dimmed" tt="uppercase">{t('project_management.current_state')}</Text>
                    <Title order={3}>
                        {showDirectDeployAlongsidePrimary
                            ? t('project_management.translation_available_title')
                            : primaryLabels[primaryAction]}
                    </Title>
                    <Text size="sm" c="dimmed">
                        {showDirectDeployAlongsidePrimary
                            ? t('project_management.translation_available_hint')
                            : t(`project_management.primary_hint.${primaryAction}`)}
                    </Text>
                </div>
                <Group gap="xs">
                    <Button data-remis-action="primary" leftSection={<PrimaryIcon size={18} />} onClick={runPrimaryAction}>
                        {primaryLabels[primaryAction]}
                    </Button>
                    {showDirectDeployAlongsidePrimary && (
                        <Button
                            variant="light"
                            leftSection={<IconRocket size={18} />}
                            onClick={handleOpenDeployModal}
                        >
                            {t('project_management.direct_deploy')}
                        </Button>
                    )}
                    <Menu position="bottom-end" withinPortal shadow="md" transitionProps={{ duration: 0 }}>
                        <Menu.Target>
                            <Button variant="default" px="xs" aria-label={t('project_management.project_menu')}>
                                <IconDotsVertical size={18} />
                            </Button>
                        </Menu.Target>
                        <Menu.Dropdown data-remis-surface="elevated" className={surfaceStyles.projectMenuDropdown}>
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

            <div className={headerStyles.stageRail} aria-label={t('project_management.project_progress', 'Project progress')}>
                <Card
                    data-remis-surface="surface"
                    data-stage-state={Number(overview.totalFiles || 0) > 0 ? 'complete' : 'pending'}
                    className={`${surfaceStyles.surfaceInset} ${headerStyles.stageCard}`}
                >
                    <Text className={headerStyles.stageLabel}>{t('project_management.stage.scan', 'Scan')}</Text>
                    <Title order={4}>{overview.totalFiles || 0}</Title>
                    <Text size="xs" c="dimmed">{t('project_management.overview.total_files')}</Text>
                </Card>
                <Card
                    data-remis-surface="surface"
                    data-stage-state={translated >= 100 ? 'complete' : 'active'}
                    className={`${surfaceStyles.surfaceInset} ${headerStyles.stageCard}`}
                >
                    <Group justify="space-between" gap="xs">
                        <Text className={headerStyles.stageLabel}>{t('project_management.stage.translation', 'Translation')}</Text>
                        <Text fw={700}>{translated}%</Text>
                    </Group>
                    <Progress value={translated} mt="xs" size="sm" radius="xl" />
                    <Text size="xs" c="dimmed" mt="xs">
                        {t('project_management.overview.to_be_proofread')}: {overview.toBeProofread || 0}%
                    </Text>
                </Card>
                <Card
                    data-remis-surface="surface"
                    data-stage-state={validationIssues > 0 ? 'blocked' : 'complete'}
                    className={`${surfaceStyles.surfaceInset} ${headerStyles.stageCard}`}
                >
                    <Text className={headerStyles.stageLabel}>{t('project_management.stage.validation', 'Validation')}</Text>
                    <Title order={4}>{validationIssues}</Title>
                    <Text size="xs" c="dimmed">
                        {validationIssues > 0
                            ? t('project_management.validation_issues', '{{count}} issues', { count: validationIssues })
                            : t('project_management.validation_ready', 'No blocking issues')}
                    </Text>
                </Card>
                <Card
                    data-remis-surface="surface"
                    data-stage-state={releaseReady ? 'complete' : 'pending'}
                    className={`${surfaceStyles.surfaceInset} ${headerStyles.stageCard}`}
                >
                    <Text className={headerStyles.stageLabel}>{t('project_management.stage.release', 'Release')}</Text>
                    <Title order={4}>
                        {releaseReady
                            ? t('project_management.release_ready', 'Ready')
                            : t('project_management.release_not_ready', 'Not ready')}
                    </Title>
                    <Text size="xs" c="dimmed">
                        {Array.isArray(projectDetails.archived_languages) && projectDetails.archived_languages.length > 0
                            ? projectDetails.archived_languages.join(', ')
                            : t('incremental_translation.none_archived')}
                    </Text>
                </Card>
            </div>
            <Group className={headerStyles.projectFacts} gap="lg" wrap="wrap">
                <Text size="xs" c="dimmed">
                    {t('project_management.overview.total_lines')}: {overview.totalLines || 0}
                </Text>
                <Text size="xs" c="dimmed">
                    {t('project_history.last_archive_time', 'Last Upload / Build')}: {' '}
                    {latestArchiveTime
                        ? formatLocalizedDateTime(latestArchiveTime, getResolvedInterfaceLocale(i18n))
                        : t('project_history.no_archive_data', 'No archive data')}
                </Text>
            </Group>
            <DeployModals deployActions={deployActions} />
        </Paper>
    );
};

export default ProjectHeader;
