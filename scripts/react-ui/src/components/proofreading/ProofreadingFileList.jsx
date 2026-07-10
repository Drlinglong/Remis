import React from 'react';
import { useTranslation } from 'react-i18next';
import { Select } from '@mantine/core';

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
        <Select
            aria-label={t('proofreading.select_source_file')}
            size="sm"
            placeholder={t('proofreading.select_source_file')}
            data={sourceFiles.map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))}
            value={currentSourceFile?.file_id}
            onChange={onSourceFileChange}
            style={{ width: '100%' }}
        />
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
        <Select
            aria-label={t('proofreading.select_translation')}
            size="sm"
            placeholder={t('proofreading.select_translation')}
            data={currentSourceFile && targetFilesMap[currentSourceFile.file_id]
                ? targetFilesMap[currentSourceFile.file_id].map(f => ({ value: f.file_id, label: f.file_path.replace(/\\/g, '/').split('/').pop() }))
                : []}
            value={currentTargetFile?.file_id}
            onChange={onTargetFileChange}
            style={{ width: '100%' }}
            disabled={!currentSourceFile}
        />
    );
};

// 保持向后兼容的默认导出（不再使用）
const ProofreadingFileList = () => null;
export default ProofreadingFileList;
