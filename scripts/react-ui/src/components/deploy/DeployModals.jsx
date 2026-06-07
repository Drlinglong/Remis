import React from 'react';
import {
    Text,
    Modal,
    Stack,
    Alert,
    Loader,
    TextInput,
    Group,
    Button,
    Code
} from '@mantine/core';
import {
    IconRocket,
    IconAlertCircle,
    IconFolderOpen,
    IconSearch
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

/**
 * Shared Modals for Deploy actions (deploy and clean)
 * 
 * @param {Object} props
 * @param {Object} props.deployActions - Output object of useDeployActions hook
 */
export function DeployModals({ deployActions }) {
    const { t } = useTranslation();
    const {
        deployModalOpen, setDeployModalOpen,
        cleanModalOpen, setCleanModalOpen,
        confirmDeleteOpen, setConfirmDeleteOpen,
        deployPath, setDeployPath,
        workshopPath, setWorkshopPath,
        loading, infoLoading,
        handleExecuteDeploy,
        handleDetectWorkshopPath,
        handleBrowseWorkshopPath,
        handleExecuteClean
    } = deployActions;

    return (
        <>
            {/* 0. 一键部署弹窗 */}
            <Modal
                opened={deployModalOpen}
                onClose={() => setDeployModalOpen(false)}
                title={<Text fw={700} size="lg">{t('button_auto_deploy')}</Text>}
                size="md"
                radius="md"
                centered
            >
                <Stack gap="md">
                    <Alert icon={<IconRocket size={20} />} title={t('button_auto_deploy')} color="blue" variant="light">
                        {t('deploy_tooltip_label')}
                    </Alert>

                    {infoLoading ? (
                        <Stack align="center" py="xl">
                            <Loader size="md" />
                            <Text size="sm">{t('deploy_loading_target_path')}</Text>
                        </Stack>
                    ) : (
                        <Stack gap="md">
                            <TextInput
                                label={t('deploy_target_path_label')}
                                placeholder={t('deploy_target_path_placeholder')}
                                description={t('deploy_target_path_desc')}
                                value={deployPath}
                                onChange={(e) => setDeployPath(e.currentTarget.value)}
                            />

                            <Group justify="flex-end" mt="lg">
                                <Button variant="default" onClick={() => setDeployModalOpen(false)} disabled={loading}>
                                    {t('cancel')}
                                </Button>
                                <Button color="blue" onClick={handleExecuteDeploy} loading={loading}>
                                    {t('deploy_btn_direct_deploy')}
                                </Button>
                            </Group>
                        </Stack>
                    )}
                </Stack>
            </Modal>

            {/* 1. 清理假本地化与部署 Modal */}
            <Modal
                opened={cleanModalOpen}
                onClose={() => setCleanModalOpen(false)}
                title={<Text fw={700} size="lg">{t('deploy_modal_title')}</Text>}
                size="lg"
                radius="md"
                centered
            >
                <Stack gap="md">
                    <Alert icon={<IconAlertCircle size={20} />} title={t('deploy_modal_title')} color="blue" variant="light">
                        {t('deploy_modal_description')}
                    </Alert>

                    {infoLoading ? (
                        <Stack align="center" py="xl">
                            <Loader size="md" />
                            <Text size="sm">{t('deploy_loading_paths')}</Text>
                        </Stack>
                    ) : (
                        <Stack gap="md">
                            <Group align="flex-end" wrap="nowrap">
                                <TextInput
                                    label={t('deploy_workshop_path_label')}
                                    placeholder={t('deploy_workshop_path_placeholder')}
                                    description={t('deploy_workshop_path_desc')}
                                    value={workshopPath}
                                    onChange={(e) => setWorkshopPath(e.currentTarget.value)}
                                    error={!workshopPath && t('deploy_workshop_path_error')}
                                    title={workshopPath}
                                    style={{ flex: 1, minWidth: 0 }}
                                    styles={{ input: { fontFamily: 'monospace' } }}
                                />
                                <Button
                                    variant="light"
                                    leftSection={<IconFolderOpen size={16} />}
                                    onClick={handleBrowseWorkshopPath}
                                    disabled={loading || infoLoading}
                                >
                                    {t('deploy_btn_browse_original_mod')}
                                </Button>
                            </Group>

                            <Group justify="space-between" mt="lg" wrap="wrap">
                                <Button variant="default" onClick={() => setCleanModalOpen(false)} disabled={loading}>
                                    {t('cancel')}
                                </Button>
                                <Group justify="flex-end" wrap="wrap">
                                    <Button
                                        variant="light"
                                        leftSection={<IconSearch size={16} />}
                                        onClick={handleDetectWorkshopPath}
                                        loading={infoLoading}
                                        disabled={loading}
                                    >
                                        {t('deploy_btn_detect_original_mod')}
                                    </Button>
                                    <Button
                                        color="red"
                                        onClick={() => setConfirmDeleteOpen(true)}
                                        loading={loading && confirmDeleteOpen}
                                        disabled={!workshopPath || loading || infoLoading}
                                    >
                                        {t('deploy_btn_delete_fake_loc')}
                                    </Button>
                                </Group>
                            </Group>
                        </Stack>
                    )}
                </Stack>
            </Modal>

            {/* 2. 高风险二次确认 Modal */}
            <Modal
                opened={confirmDeleteOpen}
                onClose={() => setConfirmDeleteOpen(false)}
                title={<Text fw={700} color="red">{t('deploy_clean_confirm_title')}</Text>}
                size="md"
                radius="md"
                centered
            >
                <Stack gap="md">
                    <Alert icon={<IconAlertCircle size={20} />} title={t('deploy_clean_confirm_title')} color="red" variant="filled">
                        {t('deploy_clean_confirm_msg')}
                    </Alert>
                    <Text size="sm" c="dimmed">
                        {t('deploy_original_mod_location')}: <Code block>{workshopPath}</Code>
                    </Text>
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={() => setConfirmDeleteOpen(false)}>
                            {t('cancel')}
                        </Button>
                        <Button color="red" onClick={handleExecuteClean} loading={loading}>
                            {t('deploy_clean_confirm_btn')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
}
