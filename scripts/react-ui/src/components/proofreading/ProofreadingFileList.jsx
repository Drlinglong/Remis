import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Group,
    Text,
    Select,
    Alert
} from '@mantine/core';
import {
    IconFileText,
    IconDatabase
} from '@tabler/icons-react';

/**
 * 文件导航组件
 * 负责源文件和目标文件的选择
 */
/**
 * 源文件选择器组件
 */
export const SourceFileSelector = ({
    sourceFiles,
    currentSourceFile,
    onSourceFileChange
}) => {
    const { t } = useTranslation();

    return (
        <>
            <Group mb={4} justify="space-between">
                <Text fw={500} size="xs">{t('proofreading.original')}</Text>
                <Select
                    size="xs"
                    placeholder="Select Source File"
                    data={sourceFiles.map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))}
                    value={currentSourceFile?.file_id}
                    onChange={onSourceFileChange}
                    style={{ width: '200px' }}
                />
            </Group>
            <Alert
                variant="light"
                color="gray"
                icon={<IconFileText size={14} />}
                style={{ marginBottom: 8, padding: '6px', minHeight: '52px', display: 'flex', alignItems: 'center' }}
                styles={{ message: { marginTop: 0 } }}
            >
                <Text size="xs" c="dimmed">
                    {t('proofreading.hint.original_source')}
                </Text>
            </Alert>

        </>
    );
};

/**
 * AI初稿选择器组件
 */
export const AIFileSelector = ({
    currentSourceFile,
    targetFilesMap,
    currentTargetFile,
    onTargetFileChange
}) => {
    const { t } = useTranslation();

    return (
        <>
            <Group mb={4} justify="space-between">
                <Text fw={500} size="xs">{t('proofreading.ai_draft')}</Text>
                <Select
                    size="xs"
                    placeholder="Select Translation"
                    data={currentSourceFile && targetFilesMap[currentSourceFile.file_id]
                        ? targetFilesMap[currentSourceFile.file_id].map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))
                        : []}
                    value={currentTargetFile?.file_id}
                    onChange={onTargetFileChange}
                    style={{ width: '200px' }}
                    disabled={!currentSourceFile}
                />
            </Group>
            <Alert
                variant="light"
                color="gray"
                icon={<IconDatabase size={14} />}
                style={{ marginBottom: 8, padding: '6px', minHeight: '52px', display: 'flex', alignItems: 'center' }}
                styles={{ message: { marginTop: 0 } }}
            >
                <Text size="xs" c="dimmed">
                    {t('proofreading.hint.ai_source')}
                </Text>
            </Alert>
        </>
    );
};

// 保持向后兼容的默认导出（不再使用）
const ProofreadingFileList = () => null;
export default ProofreadingFileList;
