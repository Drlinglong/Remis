import React from 'react';
import { useTranslation } from 'react-i18next';
import { Modal, TextInput, Button, Group, Stack } from '@mantine/core';
import { useForm } from '@mantine/form';

/**
 * 新建 SQLite 词典资产模态框
 */
const NewGlossaryModal = ({ opened, onClose, onSubmit, isLoading }) => {
    const { t } = useTranslation();

    const form = useForm({
        initialValues: { name: '' },
        validate: {
            name: (value) => {
                const normalized = value.trim();
                if (!normalized) return t('glossary_name_required');
                if (normalized.length > 200) return t('glossary_name_too_long');
                return null;
            }
        }
    });

    const handleSubmit = async (values) => {
        const success = await onSubmit(values.name.trim());
        if (success) {
            form.reset();
            onClose();
        }
    };

    return (
        <Modal
            opened={opened}
            onClose={onClose}
            title={t('glossary_create_new')}
            centered
        >
            <form onSubmit={form.onSubmit(handleSubmit)}>
                <Stack>
                    <TextInput
                        label={t('glossary_name')}
                        placeholder={t('glossary_name_placeholder')}
                        required
                        maxLength={200}
                        {...form.getInputProps('name')}
                    />
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={onClose}>
                            {t('button_cancel')}
                        </Button>
                        <Button type="submit" loading={isLoading}>
                            {t('button_create')}
                        </Button>
                    </Group>
                </Stack>
            </form>
        </Modal>
    );
};

export default NewGlossaryModal;
