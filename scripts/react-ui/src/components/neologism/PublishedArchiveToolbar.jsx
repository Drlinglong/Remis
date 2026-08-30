import React, { useMemo } from 'react';
import { Group, Paper, Select, Text } from '@mantine/core';

import RemoveModArchiveControl from './RemoveModArchiveControl';
import styles from './PublishedArchiveToolbar.module.css';

const asProjectOption = (project) => ({
    value: project.value || project.project_id,
    label: project.label || project.name || project.project_id,
});

const formatVersionDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
};

const PublishedArchiveToolbar = ({
    projects,
    selectedProject,
    onSelectedProjectChange,
    versions,
    currentRelease,
    selectedReleaseId,
    onReleaseChange,
    projectName,
    onRemoved,
    t,
    disableDelete = false,
}) => {
    const versionOptions = useMemo(() => {
        const available = versions?.length > 0 ? versions : (currentRelease ? [currentRelease] : []);
        return available.map((version) => ({
            value: version.release_id,
            label: [version.release_id, formatVersionDate(version.created_at || version.metadata?.created_at)]
                .filter(Boolean)
                .join(' · '),
        }));
    }, [currentRelease, versions]);
    const releaseValue = selectedReleaseId || currentRelease?.release_id || null;

    return (
        <Paper
            className={styles.toolbar}
            p="sm"
            withBorder
            data-remis-surface="surface"
            data-testid="published-archive-toolbar"
        >
            <Group justify="space-between" align="flex-end" gap="md" wrap="wrap">
                <Group className={styles.projectField} gap="xs" wrap="nowrap">
                    <Text className={styles.label} size="xs">{t('neologism_review.court.current_project')}</Text>
                    <Select
                        aria-label={t('neologism_review.court.current_project')}
                        data={(projects || []).map(asProjectOption)}
                        value={selectedProject}
                        onChange={onSelectedProjectChange}
                        placeholder={t('neologism_review.court.select_project')}
                        searchable
                        classNames={{ input: styles.field }}
                    />
                </Group>
                <Group className={styles.releaseControls} gap="sm" wrap="nowrap">
                    <div className={styles.versionField}>
                        <Text className={styles.label} size="xs">
                            {t('mod_archive.release.version_id', { defaultValue: 'Archive version' })}
                        </Text>
                        <Select
                            aria-label={t('mod_archive.release.version_id', { defaultValue: 'Archive version' })}
                            data={versionOptions}
                            value={releaseValue}
                            onChange={onReleaseChange}
                            placeholder={t('mod_archive.release.version_id', { defaultValue: 'Archive version' })}
                            classNames={{ input: styles.field }}
                            disabled={versionOptions.length === 0}
                        />
                    </div>
                    <RemoveModArchiveControl
                        projectId={selectedProject}
                        projectName={projectName || selectedProject}
                        onRemoved={onRemoved}
                        t={t}
                        disabled={disableDelete || !selectedProject || !currentRelease}
                        buttonLabel={t('mod_archive.release.removal.open', { defaultValue: 'Delete archive data' })}
                    />
                </Group>
            </Group>
        </Paper>
    );
};

export default PublishedArchiveToolbar;
