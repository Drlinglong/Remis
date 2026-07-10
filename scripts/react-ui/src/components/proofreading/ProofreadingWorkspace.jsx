import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Alert,
    Badge,
    Button,
    Group,
    LoadingOverlay,
    Modal,
    Paper,
    ScrollArea,
    Stack,
    Text,
} from '@mantine/core';
import {
    IconAlertCircle,
    IconAlertTriangle,
    IconCheck,
    IconDeviceFloppy,
    IconX,
} from '@tabler/icons-react';
import ProofreadingEntryWorkspace from './ProofreadingEntryWorkspace';

const ProofreadingWorkspace = ({
    rows,
    onFinalValueChange,
    validationResults,
    stats,
    loading,
    validating,
    saving,
    isDirty,
    translationChangeCount,
    commentChangeCount,
    saveModalOpen,
    variableWarnings,
    onValidate,
    onSave,
    onConfirmSave,
    onDiscardCommentChanges,
    onCancelSave,
    sourceFileSelector,
    aiFileSelector,
    query,
    onQueryChange,
    filter,
    onFilterChange,
    focusEntryKey,
    initialScrollOffset,
    onScrollOffsetChange,
    onFocusedEntryChange,
    onRequestFocusEntry,
    draftRestoreStatus,
    draftConflict,
    onDismissDraftConflict,
    externalChangeDetected,
    onReloadFromDisk,
}) => {
    const { t } = useTranslation();

    return (
        <>
            <Stack gap="sm" mb="sm">
                {externalChangeDetected && (
                    <Alert
                        color="orange"
                        icon={<IconAlertTriangle size={18} />}
                        title={t('proofreading.external_change_title', {
                            defaultValue: 'This file changed outside Remis',
                        })}
                    >
                        <Group justify="space-between" align="center">
                            <Text size="sm">
                                {t('proofreading.external_change_body', {
                                    defaultValue: 'The page is showing an older version. Reload from disk before continuing, or keep your local edits and resolve the conflict when saving.',
                                })}
                            </Text>
                            <Button size="xs" variant="light" color="orange" onClick={onReloadFromDisk}>
                                {t('proofreading.reload_from_disk', { defaultValue: 'Reload from disk' })}
                            </Button>
                        </Group>
                    </Alert>
                )}
                <Group justify="space-between">
                    <Group gap="xs">
                        <Text size="sm" fw={500} c="dimmed">{t('proofreading.mode.soft_protection')}</Text>
                        {isDirty && (
                            <Badge color="blue" variant="light">
                                {t('proofreading.unsaved_count', {
                                    defaultValue: `${translationChangeCount + commentChangeCount} unsaved changes`,
                                    count: translationChangeCount + commentChangeCount,
                                })}
                            </Badge>
                        )}
                        {draftRestoreStatus === 'restored' && (
                            <Badge color="teal" variant="light">
                                {t('proofreading.draft_restored', { defaultValue: 'Session draft restored' })}
                            </Badge>
                        )}
                    </Group>

                    <Group gap="xs">
                        <Badge color="red" leftSection={<IconX size={12} />} size="md">{stats.error}</Badge>
                        <Badge color="yellow" leftSection={<IconAlertTriangle size={12} />} size="md">{stats.warning}</Badge>
                        <Button
                            id="proofreading-validate-btn"
                            leftSection={<IconCheck size={16} />}
                            onClick={onValidate}
                            loading={validating}
                            disabled={!rows.length}
                            variant="light"
                            size="sm"
                        >
                            {t('proofreading.validate')}
                        </Button>
                        <Button
                            leftSection={<IconDeviceFloppy size={16} />}
                            onClick={onSave}
                            loading={saving}
                            disabled={!isDirty}
                            size="sm"
                        >
                            {t('proofreading.save')}
                        </Button>
                    </Group>
                </Group>
            </Stack>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, height: '100%' }}>
                <Group grow align="center" gap="sm">
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
                        query={query}
                        onQueryChange={onQueryChange}
                        filter={filter}
                        onFilterChange={onFilterChange}
                        focusEntryKey={focusEntryKey}
                        initialScrollOffset={initialScrollOffset}
                        onScrollOffsetChange={onScrollOffsetChange}
                        onFocusedEntryChange={onFocusedEntryChange}
                    />
                </div>
            </div>

            {validationResults.length > 0 && (
                <Paper withBorder p="sm" mt="sm" h={140} style={{ overflowY: 'auto' }}>
                    <Text fw={500} size="sm" mb="xs">{t('proofreading.validation_results')}</Text>
                    <Stack gap={4}>
                        {validationResults.map((result, index) => (
                            <Button
                                key={`${result.key || 'issue'}:${index}`}
                                variant="subtle"
                                color={result.level === 'error' ? 'red' : 'yellow'}
                                justify="flex-start"
                                size="compact-sm"
                                onClick={() => onRequestFocusEntry(result.key)}
                                disabled={!result.key}
                            >
                                <Group gap="xs" wrap="nowrap">
                                    <Badge color={result.level === 'error' ? 'red' : 'yellow'} size="sm">
                                        {result.level.toUpperCase()}
                                    </Badge>
                                    {result.key && <Text size="xs" ff="monospace">{result.key}</Text>}
                                    <Text size="sm">{result.message}</Text>
                                </Group>
                            </Button>
                        ))}
                    </Stack>
                </Paper>
            )}

            <Modal
                opened={saveModalOpen}
                onClose={onCancelSave}
                title={<Group><IconAlertTriangle color="var(--mantine-color-yellow-6)" /><Text fw={700}>{t('proofreading.modal.title')}</Text></Group>}
                centered
                size="lg"
            >
                <Stack>
                    {variableWarnings.length > 0 && (
                        <Alert
                            color="orange"
                            variant="light"
                            title={t('proofreading.variable_warning_title', {
                                defaultValue: 'Variable tokens changed. Review them or explicitly save anyway.',
                            })}
                            icon={<IconAlertCircle size={18} />}
                        >
                            <ScrollArea.Autosize mah={240}>
                                <Stack gap="xs">
                                    {variableWarnings.map(warning => (
                                        <Paper key={warning.entry_id} withBorder p="xs">
                                            <Text size="sm" fw={700} ff="monospace">{warning.key}</Text>
                                            {warning.changes.map(change => (
                                                <Text key={change.token} size="sm">
                                                    <Text span ff="monospace">{change.token}</Text>: {change.before} → {change.after}
                                                </Text>
                                            ))}
                                        </Paper>
                                    ))}
                                </Stack>
                            </ScrollArea.Autosize>
                        </Alert>
                    )}
                    {commentChangeCount > 0 && (
                        <Alert color="yellow" variant="light" title={t('proofreading.modal.comments_title', { count: commentChangeCount })}>
                            {t('proofreading.modal.comments_content')}
                        </Alert>
                    )}
                    <Text size="sm">
                        {t('proofreading.warning_override_hint', {
                            defaultValue: 'Warnings are advisory. Paradox scripts and source mods may intentionally contain unusual syntax.',
                        })}
                    </Text>
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={onCancelSave}>{t('proofreading.modal.button_cancel')}</Button>
                        {commentChangeCount > 0 && (
                            <Button variant="light" color="gray" onClick={onDiscardCommentChanges}>
                                {t('proofreading.modal.button_discard_comments')}
                            </Button>
                        )}
                        <Button color="orange" onClick={onConfirmSave}>
                            {t('proofreading.save_anyway', { defaultValue: 'Save anyway' })}
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={Boolean(draftConflict)}
                onClose={() => {}}
                withCloseButton={false}
                closeOnClickOutside={false}
                closeOnEscape={false}
                title={t('proofreading.draft_conflict_title', { defaultValue: 'Session draft conflict' })}
                centered
            >
                <Stack>
                    <Alert color="red" icon={<IconAlertTriangle size={18} />}>
                        {t('proofreading.draft_conflict_body', {
                            defaultValue: 'The file changed after this draft was created. The stale draft was not applied to the newer file.',
                        })}
                    </Alert>
                    <Group justify="flex-end">
                        <Button onClick={onDismissDraftConflict}>
                            {t('proofreading.use_disk_version', { defaultValue: 'Use current disk version' })}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
};

export default ProofreadingWorkspace;
