import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Paper,
    Text,
    Button,
    Group,
    Stack,
    Badge,
    Tooltip,
    LoadingOverlay,
    Alert,
    Modal
} from '@mantine/core';
import {
    IconDeviceFloppy,
    IconCheck,
    IconAlertTriangle,
    IconX,
    IconAlertCircle,
    IconFileText
} from '@tabler/icons-react';
import MonacoWrapper from '../common/MonacoWrapper';

/**
 * 校对工作区组件
 * 核心编辑区域，包含三栏编辑器、验证和保存功能
 */
const ProofreadingWorkspace = ({
    // 编辑器内容
    originalContentStr,
    aiContentStr,
    finalContentStr,
    onFinalContentChange,

    // 编辑器引用
    originalEditorRef,
    aiEditorRef,
    finalEditorRef,

    // 验证与保存
    validationResults,
    stats,
    loading,
    saving,
    keyChangeWarning,
    saveModalOpen,
    onValidate,
    onSave,
    onConfirmSave,
    onCancelSave,

    // 文件导航组件
    sourceFileSelector,
    aiFileSelector
}) => {
    const { t } = useTranslation();

    return (
        <>
            <Stack gap="xs" mb="xs">
                <Group justify="space-between">
                    <Group gap="xs">
                        <Text size="sm" c="dimmed">{t('proofreading.mode.soft_protection')}</Text>
                    </Group>

                    <Group gap="xs">
                        <Tooltip label="Errors">
                            <Badge color="red" leftSection={<IconX size={10} />} size="sm">{stats.error}</Badge>
                        </Tooltip>
                        <Tooltip label="Warnings">
                            <Badge color="yellow" leftSection={<IconAlertTriangle size={10} />} size="sm">{stats.warning}</Badge>
                        </Tooltip>

                        <Button
                            id="proofreading-validate-btn"
                            leftSection={<IconCheck size={14} />}
                            onClick={onValidate}
                            loading={loading}
                            variant="light"
                            size="xs"
                        >
                            {t('proofreading.validate')}
                        </Button>
                        <Button
                            leftSection={<IconDeviceFloppy size={14} />}
                            onClick={onSave}
                            loading={saving}
                            size="xs"
                            color={keyChangeWarning ? "red" : "blue"}
                        >
                            {t('proofreading.save')}
                        </Button>
                    </Group>
                </Group>
            </Stack>

            {/* 3-Column Layout */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'row', gap: '10px', overflow: 'hidden', width: '100%' }}>
                {/* Column 1: Original (Read Only) */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
                    {sourceFileSelector}
                    <MonacoWrapper
                        scrollRef={originalEditorRef}
                        value={originalContentStr}
                        readOnly={true}
                        theme="vs-dark"
                        language="yaml"
                    />
                </div>

                {/* Column 2: AI Draft (Read Only) */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
                    {aiFileSelector}
                    <MonacoWrapper
                        scrollRef={aiEditorRef}
                        value={aiContentStr}
                        readOnly={true}
                        theme="vs-dark"
                        language="yaml"
                    />
                </div>

                {/* Column 3: Final Edit */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
                    <Group justify="space-between" mb={4}>
                        <Text fw={500} size="xs">{t('proofreading.final_edit')}</Text>
                        {keyChangeWarning && (
                            <Badge color="red" variant="filled" size="xs" leftSection={<IconAlertTriangle size={10} />}>
                                {t('proofreading.warning.key_modified')}
                            </Badge>
                        )}
                    </Group>

                    <div style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
                        {keyChangeWarning && (
                            <Alert
                                variant="filled"
                                color="red"
                                title={t('proofreading.warning.key_modified_title')}
                                icon={<IconAlertCircle size={16} />}
                                style={{ marginBottom: 8 }}
                            >
                                <Text size="xs">
                                    {t('proofreading.warning.key_modified_desc')}
                                </Text>
                            </Alert>
                        )}

                        <Alert
                            variant="light"
                            color="gray"
                            icon={<IconFileText size={14} />}
                            style={{ marginBottom: 8, padding: '6px', minHeight: '52px', display: 'flex', alignItems: 'center' }}
                            styles={{ message: { marginTop: 0 } }}
                        >
                            <Stack gap={0}>
                                <Text size="xs" c="dimmed" fw={500}>
                                    {t('proofreading.hint.final_source')}
                                </Text>
                                <Text size="xs" c="dimmed">
                                    {t('proofreading.hint.comments_ignored')}
                                </Text>
                            </Stack>
                        </Alert>

                        <LoadingOverlay visible={loading || saving} overlayProps={{ blur: 2 }} />
                        <MonacoWrapper
                            scrollRef={finalEditorRef}
                            value={finalContentStr}
                            onChange={onFinalContentChange}
                            theme="vs-dark"
                            language="yaml"
                        />
                    </div>
                </div>
            </div>

            {/* Validation Results */}
            {validationResults.length > 0 && (
                <Paper withBorder p="xs" mt="xs" h={120} style={{ overflowY: 'auto' }}>
                    <Text fw={500} size="sm" mb="xs">{t('proofreading.validation_results')}</Text>
                    <Stack gap={4}>
                        {validationResults.map((res, idx) => (
                            <Group key={idx} gap="xs" wrap="nowrap">
                                <Badge color={res.level === 'error' ? 'red' : 'yellow'} size="xs">
                                    {res.level.toUpperCase()}
                                </Badge>
                                <Text size="xs">{res.message}</Text>
                            </Group>
                        ))}
                    </Stack>
                </Paper>
            )}

            {/* Save Confirmation Modal */}
            <Modal
                opened={saveModalOpen}
                onClose={onCancelSave}
                title={<Group><IconAlertTriangle color="red" /><Text fw={700} c="red">{t('proofreading.modal.title')}</Text></Group>}
                centered
                overlayProps={{
                    backgroundOpacity: 0.55,
                    blur: 3,
                }}
            >
                <Stack>
                    <Text size="sm">
                        <span dangerouslySetInnerHTML={{ __html: t('proofreading.modal.content_1').replace('**', '<b>').replace('**', '</b>') }} />
                    </Text>
                    <Alert color="red" variant="light">
                        <span dangerouslySetInnerHTML={{ __html: t('proofreading.modal.content_2').replace('**', '<b>').replace('**', '</b>') }} />
                    </Alert>
                    <Text size="sm" fw={500}>
                        {t('proofreading.modal.confirm')}
                    </Text>
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={onCancelSave}>{t('proofreading.modal.button_cancel')}</Button>
                        <Button color="red" onClick={onConfirmSave}>{t('proofreading.modal.button_confirm')}</Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
};

export default ProofreadingWorkspace;
