import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Group,
    Text,
    Select,
    Alert,
    Stack
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
        <Stack gap={4}>
            <Group mb={4} justify="space-between">
                <Text fw={600} size="sm">{t('proofreading.original')}</Text>
                <Select
                    size="sm"
                    placeholder={t('proofreading.select_source_file')}
                    data={sourceFiles.map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))}
                    value={currentSourceFile?.file_id}
                    onChange={onSourceFileChange}
                    style={{ width: 'clamp(200px, 18vw, 320px)' }}
                />
            </Group>
            <Alert
                variant="light"
                color="gray"
                icon={<IconFileText size={14} />}
                style={{ marginBottom: 8, padding: '8px 10px', minHeight: '54px', display: 'flex', alignItems: 'center' }}
                styles={{ message: { marginTop: 0 } }}
            >
                <Text size="sm" c="dimmed">
                    {t('proofreading.hint.original_source')}
                </Text>
            </Alert>

        </Stack>
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
        <Stack gap={4}>
            <Group mb={4} justify="space-between">
                <Text fw={600} size="sm">{t('proofreading.ai_draft')}</Text>
                <Select
                    size="sm"
                    placeholder={t('proofreading.select_translation')}
                    data={currentSourceFile && targetFilesMap[currentSourceFile.file_id]
                        ? targetFilesMap[currentSourceFile.file_id].map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))
                        : []}
                    value={currentTargetFile?.file_id}
                    onChange={onTargetFileChange}
                    style={{ width: 'clamp(200px, 18vw, 320px)' }}
                    disabled={!currentSourceFile}
                />
            </Group>
            <Alert
                variant="light"
                color="gray"
                icon={<IconDatabase size={14} />}
                style={{ marginBottom: 8, padding: '8px 10px', minHeight: '54px', display: 'flex', alignItems: 'center' }}
                styles={{ message: { marginTop: 0 } }}
            >
                <Text size="sm" c="dimmed">
                    {t('proofreading.hint.ai_source')}
                </Text>
            </Alert>
        </Stack>
    );
};

// 保持向后兼容的默认导出（不再使用）
const ProofreadingFileList = () => null;
export default ProofreadingFileList;
