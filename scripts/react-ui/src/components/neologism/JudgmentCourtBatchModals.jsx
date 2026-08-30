import React from 'react';
import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconRestore, IconX } from '@tabler/icons-react';

import styles from './JudgmentCourt.module.css';

const modalClassNames = {
    content: styles.batchModalContent,
    header: styles.batchModalHeader,
    title: styles.batchModalTitle,
    body: styles.batchModalBody,
    close: styles.batchModalClose,
};

const modalConfig = {
    approve: { color: 'blue', confirmIcon: IconCheck, noticeIcon: IconAlertTriangle },
    reject: { color: 'orange', confirmIcon: IconX, noticeIcon: IconAlertTriangle },
    restore: { color: 'blue', confirmIcon: IconRestore, noticeIcon: IconRestore },
};

const JudgmentCourtBatchModals = ({
    count,
    onClose,
    onConfirm,
    opened,
    processing,
    t,
}) => {
    const config = modalConfig[opened];
    if (!config) return null;

    const ConfirmIcon = config.confirmIcon;
    const NoticeIcon = config.noticeIcon;

    return (
        <Modal
            opened
            onClose={() => {
                if (!processing) onClose();
            }}
            title={t(`neologism_review.court.batch_${opened}_confirm_title`)}
            centered
            classNames={modalClassNames}
            closeOnClickOutside={!processing}
            closeOnEscape={!processing}
            withCloseButton={!processing}
        >
            <Stack>
                <Text>
                    {t(`neologism_review.court.batch_${opened}_confirm_message`, { count })}
                </Text>
                <Alert
                    color={config.color}
                    variant="light"
                    className={styles.batchModalAlert}
                    icon={<NoticeIcon size={18} />}
                >
                    {t(`neologism_review.court.batch_${opened}_confirm_note`)}
                </Alert>
                <Group justify="flex-end">
                    <Button
                        variant="default"
                        data-remis-action="paper-secondary"
                        onClick={onClose}
                        disabled={processing}
                    >
                        {t('neologism_review.court.batch_cancel')}
                    </Button>
                    <Button
                        color={opened === 'reject' ? 'red' : config.color}
                        data-remis-action={opened === 'reject' ? 'paper-danger' : 'paper-primary'}
                        leftSection={<ConfirmIcon size={18} />}
                        onClick={onConfirm}
                        loading={processing}
                    >
                        {t(`neologism_review.court.batch_${opened}_confirm`)}
                    </Button>
                </Group>
            </Stack>
        </Modal>
    );
};

export default JudgmentCourtBatchModals;
