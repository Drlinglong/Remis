import React from 'react';
import { Paper, Group, Title, Button, Tooltip, Grid, Card, Text, ActionIcon, Modal, TextInput, Stack, Alert, Loader, Code } from '@mantine/core';
import { IconArchive, IconRestore, IconTrash, IconSettings, IconPlayerPlay, IconRocket, IconAlertCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import styles from '../../pages/ProjectManagement.module.css';
import { useDeployActions } from '../../hooks/useDeployActions';
import { DeployModals } from '../deploy/DeployModals';

const ProjectHeader = ({ projectDetails, handleStatusChange, onDeleteForever, onManageProject }) => {
    const { t } = useTranslation();
    const navigate = useNavigate();

    const archiveSummary = projectDetails?.archive_summary || null;
    const latestArchiveTime = archiveSummary?.last_upload_at || archiveSummary?.created_at || null;

    // Shared deployment hooks
    const deployActions = useDeployActions({
        getOutputFolderName: () => {
            const outputDir = Array.isArray(projectDetails?.translation_dirs) && projectDetails.translation_dirs.length > 0
                ? projectDetails.translation_dirs[0]
                : null;
            return outputDir ? outputDir.split(/[\\/]/).pop() : projectDetails.name;
        },
        projectId: projectDetails?.project_id,
        gameId: projectDetails?.game_id
    });

    const {
        handleOpenDeployModal,
        handleOpenCleanModal
    } = deployActions;



    return (
        <Paper withBorder p="md" radius="md" className={styles.glassCard} mb="md">
            <Group justify="space-between" mb="md">
                <Title order={4}>{t('project_management.overview_title')}</Title>
                <Group>
                    {projectDetails.status === 'active' && (
                        <>
                            <Tooltip label={t('project_management.delete_project')}>
                                <Button
                                    variant="light"
                                    color="red"
                                    size="xs"
                                    leftSection={<IconTrash size={16} />}
                                    onClick={onDeleteForever}
                                >
                                    {t('project_management.delete_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.tooltip_archive')}>
                                <Button
                                    variant="light"
                                    color="orange"
                                    size="xs"
                                    leftSection={<IconArchive size={16} />}
                                    onClick={() => handleStatusChange('archived')}
                                >
                                    {t('project_management.archive_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.manage_project')}>
                                <Button
                                    variant="light"
                                    color="blue"
                                    size="xs"
                                    leftSection={<IconSettings size={16} />}
                                    onClick={onManageProject}
                                >
                                    {t('project_management.manage_project')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                    {projectDetails.status === 'archived' && (
                        <>
                            <Tooltip label={t('project_management.restore_project')}>
                                <Button variant="light" color="blue" size="xs" leftSection={<IconRestore size={16} />} onClick={() => handleStatusChange('active')}>
                                    {t('project_management.restore_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.delete_project')}>
                                <Button variant="light" color="red" size="xs" leftSection={<IconTrash size={16} />} onClick={() => handleStatusChange('deleted')}>
                                    {t('project_management.delete_project')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                    {projectDetails.status === 'deleted' && (
                        <>
                            <Tooltip label={t('project_management.restore_project')}>
                                <Button variant="light" color="blue" size="xs" leftSection={<IconRestore size={16} />} onClick={() => handleStatusChange('active')}>
                                    {t('project_management.restore_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.delete_forever')}>
                                <Button variant="filled" color="red" size="xs" leftSection={<IconTrash size={16} />} onClick={onDeleteForever}>
                                    {t('project_management.delete_forever')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                </Group>
            </Group>
            <Grid align="stretch">
                <Grid.Col span={8}>
                    <Grid id="project-stats-grid" gutter="xs">
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_files')}</Text><Title order={3}>{projectDetails.overview.totalFiles}</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_lines')}</Text><Title order={3}>{projectDetails.overview.totalLines}</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.translated')}</Text><Title order={3} c="green">{projectDetails.overview.translated}%</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.to_be_proofread')}</Text><Title order={3} c="yellow">{projectDetails.overview.toBeProofread}%</Title></Card></Grid.Col>
                        <Grid.Col span={4}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('incremental_translation.project_source_language')}</Text><Text fw={600}>{projectDetails.source_language || '--'}</Text></Card></Grid.Col>
                        <Grid.Col span={4}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('incremental_translation.archived_target_languages')}</Text><Text fw={600}>{Array.isArray(projectDetails.archived_languages) && projectDetails.archived_languages.length > 0 ? projectDetails.archived_languages.join(', ') : t('incremental_translation.none_archived')}</Text></Card></Grid.Col>
                        <Grid.Col span={4}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_history.last_archive_time', 'Last Upload / Build')}</Text><Text fw={600}>{latestArchiveTime ? new Date(latestArchiveTime).toLocaleString() : t('project_history.no_archive_data', 'No archive data')}</Text></Card></Grid.Col>
                    </Grid>
                </Grid.Col>
                <Grid.Col span={4}>
                    <Stack gap="xs" h="100%" justify="space-between">
                        <Tooltip label={t('project_management.tooltip_start_translation')}>
                            <Button
                                id="start-translation-btn"
                                fullWidth
                                h={80}
                                size="xl"
                                variant="gradient"
                                className={styles.startTranslationButton}
                                leftSection={<IconPlayerPlay size={24} className={styles.startBtnIcon} />}
                                onClick={() => navigate(`/translation?projectId=${projectDetails.project_id}`)}
                                styles={{
                                    inner: {
                                        flexDirection: 'row',
                                        gap: '8px'
                                    },
                                    label: {
                                        className: styles.startBtnLabel
                                    }
                                }}
                            >
                                <Text className={styles.startBtnLabel}>
                                    {t('button_start_translation', '开始翻译')}
                                </Text>
                            </Button>
                        </Tooltip>

                        <Group gap="xs" grow>
                            <Tooltip label={t('deploy_tooltip_label')} position="top" withArrow>
                                <Button
                                    leftSection={<IconRocket size={16} />}
                                    size="sm"
                                    color="blue"
                                    onClick={handleOpenDeployModal}
                                    fullWidth
                                >
                                    {t('button_auto_deploy', '一键部署')}
                                </Button>
                            </Tooltip>

                            <Tooltip label={t('deploy_clean_tooltip_label')} position="top" withArrow>
                                <Button
                                    leftSection={<IconTrash size={16} />}
                                    size="sm"
                                    color="red"
                                    onClick={handleOpenCleanModal}
                                    fullWidth
                                >
                                    {t('button_clean_fake_loc', '删除假本地化')}
                                </Button>
                            </Tooltip>
                        </Group>
                    </Stack>
                </Grid.Col>
            </Grid>

            <DeployModals deployActions={deployActions} />
        </Paper>
    );
};

export default ProjectHeader;
