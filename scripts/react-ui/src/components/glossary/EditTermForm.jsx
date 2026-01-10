import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import {
    Stack, Group, Title, TextInput, Textarea, Button,
    ActionIcon, Select, Switch, ScrollArea, Paper
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconX, IconPlus, IconTrash } from '@tabler/icons-react';

/**
 * 词条编辑表单组件
 * 使用 Portal 渲染到侧边栏
 */
const EditTermForm = ({
    selectedTerm,
    isCreating,
    onClose,
    onSave,
    targetLanguages,
    selectedTargetLang,
    isSaving
}) => {
    const { t } = useTranslation();
    const [isAdvancedMode, setIsAdvancedMode] = useState(false);
    const [jsonError, setJsonError] = useState(null);

    const form = useForm({
        initialValues: {
            source: '',
            translation: '',
            notes: '',
            variants: [],
            abbreviations: [],
            metadata: '',
        },
        validate: {
            source: (value) => (value.trim().length > 0 ? null : t('glossary_editor.error_source_required')),
            translation: (value) => (value.trim().length > 0 ? null : t('glossary_editor.error_translation_required')),
        },
    });

    // Load selected term data or reset for creation
    useEffect(() => {
        if (isCreating) {
            form.reset();
            form.setValues({
                source: '',
                translation: '',
                notes: '',
                variants: [],
                abbreviations: [],
                metadata: '',
            });
            setJsonError(null);
        } else if (selectedTerm) {
            const variantsArray = selectedTerm.variants
                ? Object.entries(selectedTerm.variants).map(([lang, values]) => ({
                    lang,
                    value: values.join(', ')
                }))
                : [];

            const abbreviationsArray = selectedTerm.abbreviations
                ? Object.entries(selectedTerm.abbreviations).map(([lang, value]) => ({
                    lang,
                    value
                }))
                : [];

            form.setValues({
                source: selectedTerm.source || '',
                translation: (selectedTerm.translations && selectedTerm.translations[selectedTargetLang]) || '',
                notes: selectedTerm.notes || '',
                variants: variantsArray,
                abbreviations: abbreviationsArray,
                metadata: JSON.stringify(selectedTerm.metadata || {}, null, 2),
            });
            setJsonError(null);
        }
    }, [selectedTerm, isCreating, selectedTargetLang]);

    const handleSubmit = async (values) => {
        if (jsonError) return;

        try {
            if (values.metadata) {
                JSON.parse(values.metadata);
            }
        } catch (e) {
            setJsonError(t('glossary_editor.error_invalid_json'));
            return;
        }

        const { source, translation, notes, variants, abbreviations, metadata } = values;

        const variantsObject = variants.reduce((acc, item) => {
            if (item.lang && item.value) {
                acc[item.lang] = item.value.split(',').map(s => s.trim()).filter(Boolean);
            }
            return acc;
        }, {});

        const abbreviationsObject = abbreviations.reduce((acc, item) => {
            if (item.lang && item.value) {
                acc[item.lang] = item.value;
            }
            return acc;
        }, {});

        const payload = {
            source,
            notes,
            variants: variantsObject,
            abbreviations: abbreviationsObject,
            metadata: values.metadata ? JSON.parse(values.metadata) : {},
            translations: {
                ...selectedTerm?.translations,
                [selectedTargetLang]: translation
            },
            id: selectedTerm?.id
        };

        const success = await onSave(payload);
        if (success) {
            onClose();
        }
    };

    const DynamicListEditor = ({ field, label, description }) => {
        const items = form.values[field] || [];
        return (
            <Stack>
                <span style={{ fontSize: '14px', fontWeight: 500 }}>{label}</span>
                {description && (
                    <span style={{ fontSize: '12px', color: 'dimmed', marginTop: -10, marginBottom: 5 }}>
                        {description}
                    </span>
                )}
                {items.map((item, index) => (
                    <Group key={index} wrap="nowrap">
                        <Select
                            data={targetLanguages.map(l => ({ value: l.code, label: l.name_local || l.code }))}
                            value={item.lang}
                            onChange={(value) => form.setFieldValue(`${field}.${index}.lang`, value)}
                            placeholder={t('glossary_editor.language')}
                            style={{ width: 120 }}
                        />
                        <TextInput
                            placeholder={t('glossary_editor.value')}
                            value={item.value}
                            onChange={(event) => form.setFieldValue(`${field}.${index}.value`, event.currentTarget.value)}
                            style={{ flex: 1 }}
                        />
                        <ActionIcon color="red" onClick={() => form.removeListItem(field, index)}>
                            <IconTrash size={16} />
                        </ActionIcon>
                    </Group>
                ))}
                <Button
                    leftSection={<IconPlus size={14} />}
                    variant="light"
                    fullWidth
                    onClick={() => form.insertListItem(field, { lang: '', value: '' })}
                >
                    {t('glossary_editor.add')}
                </Button>
            </Stack>
        );
    };

    if ((!selectedTerm && !isCreating) || !document.getElementById('glossary-detail-portal')) {
        return null;
    }

    return createPortal(
        <Stack gap="md" style={{ height: '100%' }}>
            <Group justify="space-between">
                <Title order={5}>{isCreating ? t('glossary_create_entry') : t('glossary_edit_entry')}</Title>
                <ActionIcon variant="subtle" onClick={onClose}>
                    <IconX size={16} />
                </ActionIcon>
            </Group>

            <form
                onSubmit={form.onSubmit(handleSubmit)}
                style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
            >
                <ScrollArea style={{ flex: 1 }}>
                    <Stack p="xs" gap="md">
                        <TextInput
                            label={t('glossary_source_text')}
                            required
                            {...form.getInputProps('source')}
                        />

                        <TextInput
                            label={`${t('glossary_translation')} (${targetLanguages.find(l => l.code === selectedTargetLang)?.name_local || selectedTargetLang
                                })`}
                            required
                            {...form.getInputProps('translation')}
                        />

                        <Textarea
                            label={t('glossary_notes')}
                            autosize
                            minRows={3}
                            {...form.getInputProps('notes')}
                        />

                        <Switch
                            label={t('glossary_advanced_mode')}
                            checked={isAdvancedMode}
                            onChange={(event) => setIsAdvancedMode(event.currentTarget.checked)}
                        />

                        {isAdvancedMode && (
                            <>
                                <DynamicListEditor
                                    field="variants"
                                    label={t('glossary_variants')}
                                    description={t('glossary_editor.variants_desc')}
                                />

                                <DynamicListEditor
                                    field="abbreviations"
                                    label={t('glossary_abbreviations')}
                                    description={t('glossary_editor.abbreviations_desc')}
                                />

                                <Textarea
                                    label={t('glossary_editor.metadata_label')}
                                    placeholder='{ "key": "value" }'
                                    autosize
                                    minRows={4}
                                    {...form.getInputProps('metadata')}
                                    error={jsonError}
                                    styles={{ input: { fontFamily: 'monospace' } }}
                                    onChange={(event) => {
                                        const val = event.currentTarget.value;
                                        form.setFieldValue('metadata', val);
                                        try {
                                            JSON.parse(val);
                                            setJsonError(null);
                                        } catch (e) {
                                            setJsonError(t('glossary_editor.error_invalid_json'));
                                        }
                                    }}
                                />
                            </>
                        )}
                    </Stack>
                </ScrollArea>

                <Paper withBorder p="sm" mt="md" radius="md" style={{ flexShrink: 0 }}>
                    <Group justify="flex-end">
                        <Button variant="default" onClick={onClose}>
                            {t('button_cancel')}
                        </Button>
                        <Button type="submit" loading={isSaving}>
                            {t('button_save')}
                        </Button>
                    </Group>
                </Paper>
            </form>
        </Stack>,
        document.getElementById('glossary-detail-portal')
    );
};

export default EditTermForm;
