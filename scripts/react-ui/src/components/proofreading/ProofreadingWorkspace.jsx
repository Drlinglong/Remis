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
    Modal,
    Tabs
} from '@mantine/core';
import {
    IconDeviceFloppy,
    IconCheck,
    IconAlertTriangle,
    IconX,
    IconAlertCircle,
    IconFileText,
    IconTable,
    IconCode
} from '@tabler/icons-react';
import MonacoWrapper from '../common/MonacoWrapper';
import ProofreadingEntryWorkspace from './ProofreadingEntryWorkspace';

/**
 * 校对工作区组件
 * 核心编辑区域，包含三栏编辑器、验证和保存功能
 */
const ProofreadingWorkspace = ({
    // 编辑器内容
    originalContentStr,
    aiContentStr,
    finalContentStr,
    rows,
    onFinalContentChange,
    onFinalValueChange,

    // 编辑器引用
    originalEditorRef,
    aiEditorRef,
    finalEditorRef,

    // 验证与保存
    validationResults,
    stats,
    loading,
    validating,
    saving,
    keyChangeWarning,
    commentChangeCount,
    saveModalOpen,
    onValidate,
    onSave,
    onConfirmSave,
    onDiscardCommentChanges,
    onCancelSave,

    // 文件导航组件
    sourceFileSelector,
    aiFileSelector
}) => {
    const { t } = useTranslation();

    return (
        <>
            <Stack gap="sm" mb="sm">
                <Group justify="space-between">
                    <Group gap="xs">
                        <Text size="sm" fw={500} c="dimmed">{t('proofreading.mode.soft_protection')}</Text>
                    </Group>

                    <Group gap="xs">
                        <Tooltip label={t('proofreading.tooltips.errors')}>
                            <Badge color="red" leftSection={<IconX size={12} />} size="md">{stats.error}</Badge>
                        </Tooltip>
                        <Tooltip label={t('proofreading.tooltips.warnings')}>
                            <Badge color="yellow" leftSection={<IconAlertTriangle size={12} />} size="md">{stats.warning}</Badge>
                        </Tooltip>

                        <Button
                            id="proofreading-validate-btn"
                            leftSection={<IconCheck size={16} />}
                            onClick={onValidate}
                            loading={validating}
                            variant="light"
                            size="sm"
                        >
                            {t('proofreading.validate')}
                        </Button>
                        <Button
                            leftSection={<IconDeviceFloppy size={16} />}
                            onClick={onSave}
                            loading={saving}
                            size="sm"
                            color={keyChangeWarning ? "red" : "blue"}
                        >
                            {t('proofreading.save')}
                        </Button>
                    </Group>
                </Group>
            </Stack>

            <Tabs defaultValue="entries" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }} styles={{ panel: { flex: 1, minHeight: 0, overflow: 'hidden' } }}>
                <Tabs.List>
                    <Tabs.Tab value="entries" leftSection={<IconTable size={16} />} fz="sm" py="sm">{t('proofreading.tabs.entries')}</Tabs.Tab>
                    <Tabs.Tab value="raw" leftSection={<IconCode size={16} />} fz="sm" py="sm">{t('proofreading.tabs.raw')}</Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="entries" pt="sm" style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, height: '100%' }}>
                        <Group grow align="flex-start">
                            {sourceFileSelector}
                            {aiFileSelector}
                        </Group>
                        <div style={{ position: 'relative', display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                            <LoadingOverlay visible={loading || validating || saving} overlayProps={{ blur: 2 }} />
                            <ProofreadingEntryWorkspace
                                rows={rows || []}
                                loading={loading}
                                validationResults={validationResults}
                                onFinalValueChange={onFinalValueChange}
                            />
                        </div>
                    </div>
                </Tabs.Panel>

                <Tabs.Panel value="raw" pt="sm" style={{ display: 'flex', flexDirection: 'column' }}>
                    {/* 3-Column Layout */}
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'row', gap: '10px', overflow: 'hidden', width: '100%', height: '100%' }}>
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
                                <Text fw={600} size="sm">{t('proofreading.final_edit')}</Text>
                                {keyChangeWarning && (
                                    <Badge color="red" variant="filled" size="sm" leftSection={<IconAlertTriangle size={12} />}>
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
                                        <Text size="sm">
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
                                        <Text size="sm" c="dimmed" fw={500}>
                                            {t('proofreading.hint.final_source')}
                                        </Text>
                                        <Text size="sm" c="dimmed">
                                            {t('proofreading.hint.comments_ignored')}
                                        </Text>
                                    </Stack>
                                </Alert>

                                <LoadingOverlay visible={loading || validating || saving} overlayProps={{ blur: 2 }} />
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
                </Tabs.Panel>
            </Tabs>

            {/* Validation Results */}
            {validationResults.length > 0 && (
                <Paper withBorder p="sm" mt="sm" h={140} style={{ overflowY: 'auto' }}>
                    <Text fw={500} size="sm" mb="xs">{t('proofreading.validation_results')}</Text>
                    <Stack gap={4}>
                        {validationResults.map((res, idx) => (
                            <Group key={idx} gap="xs" wrap="nowrap">
                                <Badge color={res.level === 'error' ? 'red' : 'yellow'} size="sm">
                                    {res.level.toUpperCase()}
                                </Badge>
                                <Text size="sm">{res.message}</Text>
                            </Group>
                        ))}
                    </Stack>
                </Paper>
            )}

            {/* Save Confirmation Modal */}
            <Modal
                opened={saveModalOpen}
                onClose={onCancelSave}
                title={<Group><IconAlertTriangle color="var(--mantine-color-yellow-6)" /><Text fw={700}>{t('proofreading.modal.title')}</Text></Group>}
                centered
                overlayProps={{
                    backgroundOpacity: 0.55,
                    blur: 3,
                }}
            >
                <Stack>
                    {keyChangeWarning && (
                        <>
                            <Text size="sm">
                                <span dangerouslySetInnerHTML={{ __html: t('proofreading.modal.content_1').replace('**', '<b>').replace('**', '</b>') }} />
                            </Text>
                            <Alert color="red" variant="light">
                                <span dangerouslySetInnerHTML={{ __html: t('proofreading.modal.content_2').replace('**', '<b>').replace('**', '</b>') }} />
                            </Alert>
                        </>
                    )}
                    {commentChangeCount > 0 && (
                        <Alert color="yellow" variant="light" title={t('proofreading.modal.comments_title', { count: commentChangeCount })}>
                            {t('proofreading.modal.comments_content')}
                        </Alert>
                    )}
                    <Text size="sm" fw={500}>
                        {t('proofreading.modal.confirm')}
                    </Text>
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={onCancelSave}>{t('proofreading.modal.button_cancel')}</Button>
                        {commentChangeCount > 0 && (
                            <Button variant="light" color="gray" onClick={onDiscardCommentChanges}>
                                {t('proofreading.modal.button_discard_comments')}
                            </Button>
                        )}
                        <Button onClick={onConfirmSave}>{t('proofreading.modal.button_confirm')}</Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
};

export default ProofreadingWorkspace;
