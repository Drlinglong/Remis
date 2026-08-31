import React, { useEffect, useRef, useState } from 'react';
import {
    ActionIcon,
    Badge,
    Button,
    Divider,
    Group,
    Modal,
    PasswordInput,
    Select,
    Stack,
    TagsInput,
    Text,
    TextInput,
    Textarea,
} from '@mantine/core';
import { IconEdit, IconKey, IconPlus, IconServer, IconTrash, IconRobot } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import ProviderReasoningSettings from './ProviderReasoningSettings';
import { parseCustomParameters } from './reasoningForm';
import {
    useCustomProviderProfiles,
} from './useCustomProviderProfiles';
import { isValidProviderBaseUrl } from './customProviderProfileForm';
import { formatApiError } from '../../utils/apiErrors';
import styles from './CustomProviderProfiles.module.css';

const ADAPTER_ID = 'your_favourite_api';

const profileToForm = (profile) => ({
    displayName: profile.display_name || profile.name || 'Custom Provider',
    apiKey: '',
    models: profile.models || profile.custom_models || [],
    apiUrl: profile.api_url || '',
    selectedModel: profile.selected_model || '',
    promptPrefix: profile.prompt_prefix || '',
    systemPromptSuffix: profile.system_prompt_suffix || '',
    reasoningBuiltinEnabled: Boolean(profile.reasoning?.builtin_enabled ?? profile.reasoning_builtin_enabled),
    reasoningPreset: profile.reasoning?.selected_preset || profile.reasoning_preset || 'medium',
    customParametersText: Object.keys(profile.reasoning?.custom_parameters || profile.custom_parameters || {}).length
        ? JSON.stringify(profile.reasoning?.custom_parameters || profile.custom_parameters, null, 2)
        : '',
});

const formToPayload = (form) => {
    const payload = {
        display_name: form.displayName.trim() || 'Custom Provider',
        models: form.models,
        api_url: form.apiUrl.trim(),
        selected_model: form.selectedModel.trim(),
        prompt_prefix: form.promptPrefix,
        system_prompt_suffix: form.systemPromptSuffix,
        reasoning_builtin_enabled: form.reasoningBuiltinEnabled,
        reasoning_preset: form.reasoningPreset,
        custom_parameters: parseCustomParameters(form.customParametersText),
    };
    if (form.apiKey.trim()) {
        payload.api_key = form.apiKey.trim();
    }
    return payload;
};

const getProfileLabel = (profile) => profile.display_name || profile.name || profile.profile_id;

const CustomProviderProfileCard = ({
    profile,
    editing,
    form,
    submitting,
    onEdit,
    onChange,
    onSave,
    onCancel,
    onDelete,
    t,
}) => {
    const apiUrlValid = isValidProviderBaseUrl(form.apiUrl);
    const reasoningCapability = profile.reasoning_models?.[form.selectedModel];
    const reasoningPresets = reasoningCapability?.presets || {};
    const effectiveReasoning = {
        ...profile.reasoning,
        supported: Boolean(reasoningCapability),
        available_presets: Object.keys(reasoningPresets),
        mapping_preview: reasoningPresets[form.reasoningPreset] || {},
    };
    const availableModels = [
        ...(profile.available_models || []),
        ...(form.models || []),
        ...(form.selectedModel ? [form.selectedModel] : []),
    ].filter((value, index, values) => value && values.indexOf(value) === index);

    return (
        <article className={styles.card}>
            <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>
                    <Group gap="xs" wrap="wrap">
                        <Text fw={600}>{getProfileLabel(profile)}</Text>
                        {profile.has_key && <Badge color="green" variant="light">{t('api_key_active')}</Badge>}
                    </Group>
                    <Text size="xs" c="dimmed" mt={4}>{profile.profile_id}</Text>
                </div>
                {!editing && (
                    <div className={styles.cardActions}>
                        <ActionIcon
                            variant="subtle"
                            aria-label={t('custom_profiles_edit')}
                            onClick={onEdit}
                        >
                            <IconEdit size={16} />
                        </ActionIcon>
                        <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t('custom_profiles_delete')}
                            onClick={onDelete}
                        >
                            <IconTrash size={16} />
                        </ActionIcon>
                    </div>
                )}
            </div>

            {editing ? (
                <div className={styles.form}>
                    <TextInput
                        label={t('custom_profiles_name_label')}
                        value={form.displayName}
                        onChange={(event) => onChange({ displayName: event.currentTarget.value })}
                        autoFocus
                    />
                    <TextInput
                        label={t('api_url_label', 'API Base URL')}
                        value={form.apiUrl}
                        onChange={(event) => onChange({ apiUrl: event.currentTarget.value })}
                        leftSection={<IconServer size={14} />}
                        required
                        error={form.apiUrl && !apiUrlValid ? t('api_url_openai_compatible_help') : null}
                    />
                    <PasswordInput
                        label={t('api_key_label', 'API Key')}
                        placeholder={profile.has_key ? t('custom_profiles_key_keep') : t('api_key_placeholder')}
                        value={form.apiKey}
                        onChange={(event) => onChange({ apiKey: event.currentTarget.value })}
                        leftSection={<IconKey size={14} />}
                    />
                    <Select
                        label={t('api_model_select_label', 'Active Translation Model')}
                        data={availableModels.map((model) => ({ value: model, label: model }))}
                        value={form.selectedModel}
                        onChange={(value) => {
                            const capability = profile.reasoning_models?.[value];
                            const presets = Object.keys(capability?.presets || {});
                            onChange({
                                selectedModel: value || '',
                                reasoningBuiltinEnabled: capability ? form.reasoningBuiltinEnabled : false,
                                reasoningPreset: presets.includes(form.reasoningPreset)
                                    ? form.reasoningPreset
                                    : (presets[0] || 'medium'),
                            });
                        }}
                        searchable
                        clearable
                        leftSection={<IconRobot size={14} />}
                        required
                    />
                    <TagsInput
                        label={t('api_models_label', 'Custom Models')}
                        value={form.models}
                        onChange={(models) => onChange({
                            models,
                            selectedModel: form.selectedModel || models[0] || '',
                        })}
                        placeholder={t('api_models_placeholder', 'Type and press Enter to add models')}
                    />
                    <Divider label={t('api_prompt_controls_label', 'Prompt Controls')} labelPosition="center" />
                    <TextInput
                        label={t('api_prompt_prefix_label', 'User Prompt Prefix')}
                        value={form.promptPrefix}
                        onChange={(event) => onChange({ promptPrefix: event.currentTarget.value })}
                    />
                    <Textarea
                        label={t('api_system_prompt_suffix_label', 'System Prompt Suffix')}
                        value={form.systemPromptSuffix}
                        onChange={(event) => onChange({ systemPromptSuffix: event.currentTarget.value })}
                        autosize
                        minRows={2}
                    />
                    <Divider label={t('api_reasoning_controls_label')} labelPosition="center" />
                    <ProviderReasoningSettings
                        reasoning={effectiveReasoning}
                        form={form}
                        onChange={onChange}
                    />
                    <div className={styles.formActions}>
                        <Button
                            size="xs"
                            loading={submitting}
                            disabled={!apiUrlValid || !form.selectedModel.trim()}
                            onClick={onSave}
                        >
                            {t('save')}
                        </Button>
                        <Button size="xs" variant="subtle" color="gray" disabled={submitting} onClick={onCancel}>
                            {t('cancel')}
                        </Button>
                    </div>
                </div>
            ) : (
                <div className={styles.summary}>
                    <div className={styles.summaryRow}>
                        <Text size="xs" c="dimmed">{t('settings_api_label_key')}</Text>
                        <Text className={styles.summaryValue} size="xs" family="monospace">
                            {profile.has_key ? (profile.masked_key || profile.masked_api_key || '••••••••') : t('api_key_none_set')}
                        </Text>
                    </div>
                    <div className={styles.summaryRow}>
                        <Text size="xs" c="dimmed">{t('settings_api_label_url')}</Text>
                        <Text className={styles.summaryValue} size="xs" title={profile.api_url || ''}>
                            {profile.api_url || 'N/A'}
                        </Text>
                    </div>
                    <div className={styles.summaryRow}>
                        <Text size="xs" c="dimmed">{t('settings_api_label_model')}</Text>
                        <Text className={styles.summaryValue} size="xs">{profile.selected_model || 'N/A'}</Text>
                    </div>
                    <div className={styles.summaryRow}>
                        <Text size="xs" c="dimmed">{t('custom_profiles_adapter_label')}</Text>
                        <Text className={styles.summaryValue} size="xs">{profile.adapter_id}</Text>
                    </div>
                </div>
            )}
        </article>
    );
};

const noop = () => undefined;

const CustomProviderProfiles = ({ onDirtyChange = noop, discardToken = 0 }) => {
    const { t } = useTranslation();
    const {
        profiles,
        loading,
        error,
        createProfile,
        updateProfile,
        deleteProfile,
    } = useCustomProviderProfiles();
    const [editingId, setEditingId] = useState(null);
    const [forms, setForms] = useState({});
    const [originalForms, setOriginalForms] = useState({});
    const [drafts, setDrafts] = useState([]);
    const [submittingId, setSubmittingId] = useState(null);
    const [pendingDelete, setPendingDelete] = useState(null);
    const previousDiscardToken = useRef(discardToken);

    const displayedProfiles = [...profiles, ...drafts];

    useEffect(() => {
        if (previousDiscardToken.current === discardToken) return;
        previousDiscardToken.current = discardToken;
        setEditingId(null);
        setForms({});
        setOriginalForms({});
        setDrafts([]);
        onDirtyChange(false);
    }, [discardToken, onDirtyChange]);

    const editingProfile = displayedProfiles.find((profile) => profile.profile_id === editingId);
    const currentEditingForm = editingId ? forms[editingId] : null;
    const originalEditingForm = editingId ? originalForms[editingId] : null;
    const currentEditingDirty = Boolean(
        editingId
        && (editingProfile?.isDraft
            || JSON.stringify(currentEditingForm) !== JSON.stringify(originalEditingForm)),
    );
    useEffect(() => {
        const formChanged = Boolean(
            editingId
            && JSON.stringify(currentEditingForm) !== JSON.stringify(originalEditingForm),
        );
        onDirtyChange(Boolean(formChanged || editingProfile?.isDraft));
    }, [currentEditingForm, editingId, editingProfile?.isDraft, onDirtyChange, originalEditingForm]);

    const notifyError = (requestError) => {
        notifications.show({
            title: t('error'),
            message: formatApiError(requestError, t('notification.error_generic')),
            color: 'red',
        });
    };

    const beginEdit = (profile) => {
        if (editingId && editingId !== profile.profile_id && currentEditingDirty) {
            notifications.show({
                title: t('settings_unsaved_changes_title'),
                message: t('settings_unsaved_changes_message'),
                color: 'yellow',
            });
            return;
        }
        const nextForm = profileToForm(profile);
        setEditingId(profile.profile_id);
        setForms((current) => ({ ...current, [profile.profile_id]: nextForm }));
        setOriginalForms((current) => ({ ...current, [profile.profile_id]: nextForm }));
    };

    const handleAdd = () => {
        if (currentEditingDirty) {
            notifications.show({
                title: t('settings_unsaved_changes_title'),
                message: t('settings_unsaved_changes_message'),
                color: 'yellow',
            });
            return;
        }
        const profileId = `draft-${Date.now()}`;
        const draft = {
            profile_id: profileId,
            display_name: t('custom_profiles_new_name'),
            adapter_id: ADAPTER_ID,
            models: [],
            api_url: '',
            selected_model: '',
            has_key: false,
            reasoning: { supported: false, custom_parameters: {} },
            isDraft: true,
        };
        const initialForm = profileToForm(draft);
        setDrafts((current) => [...current, draft]);
        setEditingId(profileId);
        setForms((current) => ({ ...current, [profileId]: initialForm }));
        setOriginalForms((current) => ({ ...current, [profileId]: initialForm }));
    };

    const handleSave = async (profile) => {
        const form = forms[profile.profile_id] || profileToForm(profile);
        setSubmittingId(profile.profile_id);
        try {
            if (profile.isDraft) {
                await createProfile(formToPayload(form));
                setDrafts((current) => current.filter((item) => item.profile_id !== profile.profile_id));
            } else {
                await updateProfile(profile.profile_id, formToPayload(form));
            }
            setEditingId(null);
            notifications.show({
                title: t('success'),
                message: t('custom_profiles_saved'),
                color: 'green',
            });
        } catch (requestError) {
            notifyError(requestError);
        } finally {
            setSubmittingId(null);
        }
    };

    const handleCancel = (profile) => {
        if (profile.isDraft) {
            setDrafts((current) => current.filter((item) => item.profile_id !== profile.profile_id));
            setForms((current) => {
                const next = { ...current };
                delete next[profile.profile_id];
                return next;
            });
            setOriginalForms((current) => {
                const next = { ...current };
                delete next[profile.profile_id];
                return next;
            });
        }
        setEditingId(null);
    };

    const handleDelete = async () => {
        if (!pendingDelete) return;
        const profileId = pendingDelete.profile_id;
        setSubmittingId(profileId);
        try {
            if (pendingDelete.isDraft) {
                setDrafts((current) => current.filter((item) => item.profile_id !== profileId));
            } else {
                await deleteProfile(profileId);
            }
            if (editingId === profileId) setEditingId(null);
            setForms((current) => {
                const next = { ...current };
                delete next[profileId];
                return next;
            });
            setOriginalForms((current) => {
                const next = { ...current };
                delete next[profileId];
                return next;
            });
            setPendingDelete(null);
            notifications.show({
                title: t('success'),
                    message: t('custom_profiles_deleted'),
                color: 'green',
            });
        } catch (requestError) {
            notifyError(requestError);
        } finally {
            setSubmittingId(null);
        }
    };

    if (loading) {
        return <Text size="sm" c="dimmed">{t('custom_profiles_loading')}</Text>;
    }

    return (
        <section className={styles.section} aria-labelledby="custom-provider-profiles-title">
            <div className={styles.sectionHeader}>
                <div>
                    <Text id="custom-provider-profiles-title" fw={600}>{t('custom_profiles_title')}</Text>
                    <Text size="sm" c="dimmed">{t('custom_profiles_description')}</Text>
                </div>
                <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={handleAdd}
                >
                    {t('custom_profiles_add')}
                </Button>
            </div>

            {error && <Text size="sm" c="red">{t('custom_profiles_load_error')}</Text>}

            {displayedProfiles.length === 0 ? (
                <Text size="sm" c="dimmed" mt="md">{t('custom_profiles_empty')}</Text>
            ) : (
                <div className={styles.grid}>
                    {displayedProfiles.map((profile) => {
                        const profileId = profile.profile_id;
                        const form = forms[profileId] || profileToForm(profile);
                        return (
                            <CustomProviderProfileCard
                                key={profileId}
                                profile={profile}
                                editing={editingId === profileId}
                                form={form}
                                submitting={submittingId === profileId}
                                onEdit={() => beginEdit(profile)}
                                onChange={(changes) => setForms((current) => ({
                                    ...current,
                                    [profileId]: { ...form, ...changes },
                                }))}
                                onSave={() => handleSave(profile)}
                                onCancel={() => handleCancel(profile)}
                                onDelete={() => setPendingDelete(profile)}
                                t={t}
                            />
                        );
                    })}
                </div>
            )}

            <Modal
                opened={Boolean(pendingDelete)}
                onClose={() => setPendingDelete(null)}
                title={t('custom_profiles_delete_title')}
                centered
            >
                <Stack>
                    <Text>{t('custom_profiles_delete_message', { name: pendingDelete ? getProfileLabel(pendingDelete) : '' })}</Text>
                    <Group justify="flex-end">
                        <Button variant="subtle" onClick={() => setPendingDelete(null)}>
                            {t('cancel')}
                        </Button>
                        <Button color="red" loading={submittingId === pendingDelete?.profile_id} onClick={handleDelete}>
                            {t('custom_profiles_delete_confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </section>
    );
};

export default CustomProviderProfiles;
