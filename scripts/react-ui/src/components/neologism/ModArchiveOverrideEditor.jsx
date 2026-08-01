import React, { useMemo, useState } from 'react';
import {
    Alert,
    Badge,
    Button,
    Group,
    Modal,
    Paper,
    Select,
    Stack,
    Text,
    Textarea,
    Title,
} from '@mantine/core';
import { IconAlertCircle, IconCheck, IconEdit, IconGitBranch } from '@tabler/icons-react';

import { ARCHIVE_OVERRIDE_FIELD_KEYS } from './modArchiveModel';
import styles from './ModArchive.module.css';

const MULTILINE_FIELDS = new Set(['summary', 'relationship_correction']);

const fieldLabelKey = (fieldKey) => `mod_archive.release.draft.field_${fieldKey}`;

const safeDisplayValue = (value, t) => {
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value) && value.length > 0) return value.join(', ');
    if (value && typeof value === 'object' && typeof value.summary === 'string') return value.summary;
    return t('mod_archive.release.draft.structured_value');
};

const getUnknownFields = (overrides) => overrides.flatMap((override) => {
    const unknownKeys = Object.keys(override?.value || {})
        .filter((key) => !ARCHIVE_OVERRIDE_FIELD_KEYS.includes(key));
    return unknownKeys.map((key) => ({ targetKey: override.target_key, key }));
});

const InheritedOverrides = ({ overrides, t }) => {
    const unknownFields = getUnknownFields(overrides);
    if (overrides.length === 0 && unknownFields.length === 0) {
        return <Text className={styles.muted} size="sm">{t('mod_archive.release.draft.no_inherited')}</Text>;
    }

    return (
        <Stack gap="xs" data-testid="mod-archive-inherited-overrides">
            {overrides.map((override) => {
                const knownValues = Object.entries(override?.value || {})
                    .filter(([key]) => ARCHIVE_OVERRIDE_FIELD_KEYS.includes(key));
                return (
                    <Paper className={styles.inheritedRow} key={override.target_key} data-remis-surface="paper">
                        <Group justify="space-between" align="flex-start" wrap="nowrap">
                            <Text className={styles.technical} size="sm">{override.target_key}</Text>
                            <Badge variant="light">{t('mod_archive.release.draft.inherited_badge')}</Badge>
                        </Group>
                        {knownValues.map(([key, value]) => (
                            <Text size="sm" key={key} mt={4}>
                                {t(fieldLabelKey(key))}: {safeDisplayValue(value, t)}
                            </Text>
                        ))}
                        {override.note && (
                            <Text className={styles.muted} size="xs" mt={4}>
                                {t('mod_archive.release.draft.note_label')}: {override.note}
                            </Text>
                        )}
                    </Paper>
                );
            })}
            {unknownFields.length > 0 && (
                <Alert className={styles.notice} data-remis-surface="surface" icon={<IconAlertCircle size={16} />}>
                    <Text fw={600}>{t('mod_archive.release.draft.unknown_title')}</Text>
                    <Text size="sm">{t('mod_archive.release.draft.unknown_desc')}</Text>
                    <Stack gap={2} mt="xs">
                        {unknownFields.map((item) => (
                            <Text className={styles.technical} size="xs" key={`${item.targetKey}:${item.key}`}>
                                {item.targetKey} · {item.key}
                            </Text>
                        ))}
                    </Stack>
                </Alert>
            )}
        </Stack>
    );
};

const DraftError = ({ error, t }) => {
    if (!error?.message) return null;
    return (
        <Alert
            className={`${styles.statusSurface} ${styles.notice}`}
            data-tone="error"
            data-testid="mod-archive-draft-error"
            icon={<IconAlertCircle size={18} />}
        >
            <Text fw={600}>{error.message}</Text>
            {error.code && (
                <details className={styles.errorDetails}>
                    <summary>{t('mod_archive.release.draft.error_details')}</summary>
                    <Text className={styles.technical} size="xs">{error.code}</Text>
                </details>
            )}
        </Alert>
    );
};

const ModArchiveOverrideEditor = ({
    draftState,
    contextEntries,
    baseReleaseId,
    t,
}) => {
    const [publishConfirmationOpen, setPublishConfirmationOpen] = useState(false);
    const {
        phase,
        draft,
        selectedKey,
        fieldValues,
        note,
        error,
        notice,
        inheritedOverrides,
        selectContextKey,
        updateField,
        setNote,
        saveOverride,
        publishDraft,
    } = draftState;
    const entryOptions = useMemo(() => contextEntries.map((entry) => ({
        value: entry.key,
        label: entry.label || entry.key,
    })), [contextEntries]);
    const isSaving = phase === 'saving';
    const isPublishing = phase === 'publishing';
    const isBusy = isSaving || isPublishing;

    const handlePublish = async () => {
        const published = await publishDraft();
        if (published) setPublishConfirmationOpen(false);
    };

    if (!draft) return null;

    return (
        <Paper
            className={styles.draftEditor}
            p="lg"
            mt="md"
            withBorder
            data-testid="mod-archive-draft-editor"
            data-remis-surface="surface"
        >
            <Stack gap="md">
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                    <Group gap="sm" wrap="nowrap">
                        <Badge className={styles.headerIcon} size="lg" radius="sm">
                            <IconEdit size={18} />
                        </Badge>
                        <div>
                            <Title order={3}>{t('mod_archive.release.draft.title')}</Title>
                            <Text className={styles.muted} size="sm">
                                {t('mod_archive.release.draft.subtitle')}
                            </Text>
                        </div>
                    </Group>
                    <Badge variant="outline" data-testid="mod-archive-draft-status">
                        {t('mod_archive.release.draft.status')}
                    </Badge>
                </Group>

                <div className={styles.metadataGrid}>
                    <div className={styles.metadataCell}>
                        <Text className={styles.metadataLabel}>{t('mod_archive.release.draft.draft_id')}</Text>
                        <Text className={styles.technical} size="sm">{draft.draft_id}</Text>
                    </div>
                    <div className={styles.metadataCell}>
                        <Text className={styles.metadataLabel}>{t('mod_archive.release.draft.base_release')}</Text>
                        <Text className={styles.technical} size="sm">{baseReleaseId}</Text>
                    </div>
                </div>

                <div>
                    <Title order={4}>{t('mod_archive.release.draft.inherited_title')}</Title>
                    <Text className={styles.muted} size="sm" mb="xs">
                        {t('mod_archive.release.draft.inherited_desc')}
                    </Text>
                    <InheritedOverrides overrides={inheritedOverrides} t={t} />
                </div>

                <div className={styles.draftForm}>
                    <Title order={4}>{t('mod_archive.release.draft.edit_title')}</Title>
                    <Text className={styles.muted} size="sm">
                        {t('mod_archive.release.draft.edit_desc')}
                    </Text>
                    {entryOptions.length > 0 ? (
                        <Select
                            label={t('mod_archive.release.draft.select_entry')}
                            placeholder={t('mod_archive.release.draft.select_entry_placeholder')}
                            data={entryOptions}
                            value={selectedKey}
                            onChange={selectContextKey}
                            disabled={isBusy}
                            searchable
                            data-testid="mod-archive-draft-key"
                        />
                    ) : (
                        <Text className={styles.muted} size="sm" data-testid="mod-archive-draft-no-entries">
                            {t('mod_archive.release.draft.no_entries')}
                        </Text>
                    )}
                    <div className={styles.draftFieldGrid}>
                        {ARCHIVE_OVERRIDE_FIELD_KEYS.map((fieldKey) => (
                            <Textarea
                                key={fieldKey}
                                className={styles.draftField}
                                label={t(fieldLabelKey(fieldKey))}
                                description={fieldKey === 'summary'
                                    ? t('mod_archive.release.draft.field_helper')
                                    : undefined}
                                placeholder={t(`mod_archive.release.draft.placeholder_${fieldKey}`)}
                                minRows={MULTILINE_FIELDS.has(fieldKey) ? 3 : 1}
                                autosize={MULTILINE_FIELDS.has(fieldKey)}
                                value={fieldValues[fieldKey] || ''}
                                onChange={(event) => updateField(fieldKey, event.currentTarget.value)}
                                disabled={isBusy || !selectedKey}
                                data-testid={`mod-archive-draft-field-${fieldKey}`}
                            />
                        ))}
                    </div>
                    <Textarea
                        label={t('mod_archive.release.draft.note_label')}
                        description={t('mod_archive.release.draft.note_desc')}
                        placeholder={t('mod_archive.release.draft.note_placeholder')}
                        minRows={2}
                        autosize
                        value={note}
                        onChange={(event) => setNote(event.currentTarget.value)}
                        disabled={isBusy || !selectedKey}
                        data-testid="mod-archive-draft-note"
                    />
                    <Text className={styles.muted} size="xs">
                        {t('mod_archive.release.draft.clear_not_supported')}
                    </Text>
                </div>

                <DraftError error={error} t={t} />
                {notice?.type === 'saved' && (
                    <Alert className={styles.notice} data-tone="success" icon={<IconCheck size={18} />}>
                        {t('mod_archive.release.draft.save_success')}
                    </Alert>
                )}
                <Group justify="space-between" align="center" wrap="wrap" className={styles.draftActions}>
                    <Text className={styles.muted} size="sm">
                        {t('mod_archive.release.draft.published_read_only')}
                    </Text>
                    <Group gap="sm">
                        <Button
                            className={styles.primaryAction}
                            onClick={saveOverride}
                            loading={isSaving}
                            disabled={isBusy || !selectedKey}
                            data-remis-action="primary"
                            data-testid="mod-archive-save-override"
                        >
                            {t('mod_archive.release.draft.save_override')}
                        </Button>
                        <Button
                            className={styles.secondaryAction}
                            variant="outline"
                            leftSection={<IconGitBranch size={16} />}
                            onClick={() => setPublishConfirmationOpen(true)}
                            disabled={isBusy}
                            data-remis-action="secondary"
                            data-testid="mod-archive-open-publish"
                        >
                            {t('mod_archive.release.draft.publish_new_version')}
                        </Button>
                    </Group>
                </Group>
            </Stack>

            <Modal
                opened={publishConfirmationOpen}
                onClose={() => setPublishConfirmationOpen(false)}
                title={t('mod_archive.release.draft.publish_title')}
                centered
                data-remis-surface="elevated"
                data-testid="mod-archive-publish-modal"
            >
                <Stack gap="md">
                    <Text>{t('mod_archive.release.draft.publish_desc')}</Text>
                    <Text className={styles.muted} size="sm">
                        {t('mod_archive.release.draft.publish_base', { releaseId: baseReleaseId })}
                    </Text>
                    <Group justify="flex-end">
                        <Button
                            className={styles.secondaryAction}
                            variant="outline"
                            onClick={() => setPublishConfirmationOpen(false)}
                            disabled={isPublishing}
                            data-remis-action="secondary"
                        >
                            {t('mod_archive.release.draft.publish_cancel')}
                        </Button>
                        <Button
                            className={styles.primaryAction}
                            onClick={handlePublish}
                            loading={isPublishing}
                            data-remis-action="primary"
                            data-testid="mod-archive-publish-confirm"
                        >
                            {t('mod_archive.release.draft.publish_confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </Paper>
    );
};

export default ModArchiveOverrideEditor;
