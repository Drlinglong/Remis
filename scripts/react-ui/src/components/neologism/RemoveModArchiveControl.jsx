import React from 'react';
import { Alert, Button, Code, Group, Modal, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconTrash } from '@tabler/icons-react';

import styles from './ModArchive.module.css';
import { useRemoveModArchive } from './useRemoveModArchive';

const modalClassNames = {
    content: styles.removalModalContent,
    header: styles.removalModalHeader,
    title: styles.removalModalTitle,
    body: styles.removalModalBody,
    close: styles.removalModalClose,
};

const RemoveModArchiveControl = ({
    projectId,
    projectName,
    onRemoved,
    t,
    buttonLabel,
    disabled = false,
}) => {
    const removal = useRemoveModArchive({ projectId, projectName, onRemoved, t });

    return (
        <>
            <Button
                className={styles.dangerSecondaryAction}
                leftSection={<IconTrash size={16} />}
                onClick={removal.open}
                disabled={disabled}
                variant="default"
                data-testid="mod-archive-remove"
            >
                {buttonLabel || t('mod_archive.release.removal.open')}
            </Button>
            <Modal
                opened={removal.opened}
                onClose={removal.close}
                title={t('mod_archive.release.removal.title')}
                classNames={modalClassNames}
                data-remis-surface="elevated"
                centered
            >
                <Stack gap="md" data-remis-surface="elevated">
                    <Alert
                        className={styles.removalWarning}
                        icon={<IconAlertTriangle size={18} />}
                        title={t('mod_archive.release.removal.warning_title')}
                    >
                        {t('mod_archive.release.removal.warning_desc')}
                    </Alert>
                    <Text>{t('mod_archive.release.removal.confirm', { project: projectName })}</Text>
                    <Code className={styles.removalProjectName} block>{projectName}</Code>
                    <Text className={styles.removalMuted} size="sm">
                        {t('mod_archive.release.removal.preserved')}
                    </Text>
                    {removal.error && (
                        <Alert className={styles.removalWarning} data-testid="mod-archive-removal-error">
                            {removal.error}
                        </Alert>
                    )}
                    <Group justify="flex-end">
                        <Button
                            className={styles.removalCancel}
                            onClick={removal.close}
                            disabled={removal.removing}
                            variant="default"
                        >
                            {t('mod_archive.release.removal.cancel')}
                        </Button>
                        <Button
                            color="red"
                            loading={removal.removing}
                            onClick={removal.remove}
                            data-testid="mod-archive-confirm-remove"
                        >
                            {t('mod_archive.release.removal.confirm_action')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </>
    );
};

export default RemoveModArchiveControl;
