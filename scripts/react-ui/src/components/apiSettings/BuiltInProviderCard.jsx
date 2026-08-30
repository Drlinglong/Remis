import React from 'react';
import {
    ActionIcon,
    Badge,
    Button,
    Divider,
    Group,
    PasswordInput,
    Select,
    Stack,
    TagsInput,
    Text,
    TextInput,
    Textarea,
    Tooltip,
} from '@mantine/core';
import {
    IconCheck,
    IconEdit,
    IconInfoCircle,
    IconKey,
    IconMessage,
    IconRobot,
    IconServer,
} from '@tabler/icons-react';
import ProviderReasoningSettings from './ProviderReasoningSettings';
import styles from '../ApiSettingsTab.module.css';

const URL_EDITABLE_PROVIDER_IDS = ['lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui', 'ollama'];
const LOCAL_OPENAI_PROVIDER_IDS = ['lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];
const OLLAMA_PROVIDER_ID = 'ollama';
const CONCRETE_OPENAI_ENDPOINTS = ['/responses', '/chat/completions'];

const isConcreteOpenAIEndpoint = (providerId, apiUrl) => {
    if (!LOCAL_OPENAI_PROVIDER_IDS.includes(providerId) || !apiUrl) return false;
    const normalized = apiUrl.trim().replace(/\/+$/, '').toLowerCase();
    return CONCRETE_OPENAI_ENDPOINTS.some((endpoint) => normalized.endsWith(endpoint));
};

const getApiUrlPlaceholder = (providerId) => {
    if (providerId === OLLAMA_PROVIDER_ID) return 'http://localhost:11434';
    if (LOCAL_OPENAI_PROVIDER_IDS.includes(providerId)) return 'http://localhost:1234/v1';
    return 'https://api.example.com/v1';
};

const BuiltInProviderCard = ({
    provider,
    editing,
    editForm,
    submitting,
    testingConnection,
    t,
    setEditForm,
    handleSave,
    handleCancelEdit,
    handleEditClick,
    handleTestConnection,
}) => {
    if (!provider) return null;

    const canEditUrl = URL_EDITABLE_PROVIDER_IDS.includes(provider.id);
    const isLocalOpenAIProvider = LOCAL_OPENAI_PROVIDER_IDS.includes(provider.id);
    const isOllamaProvider = provider.id === OLLAMA_PROVIDER_ID;
    const apiUrlError = isConcreteOpenAIEndpoint(provider.id, editForm.apiUrl)
        ? t('api_url_endpoint_error')
        : null;
    const apiUrlHelp = isOllamaProvider
        ? t('api_url_ollama_help')
        : isLocalOpenAIProvider
            ? t('api_url_openai_compatible_help')
            : t('api_url_generic_help');
    const selectedReasoningCapability = provider.reasoning_models?.[editForm.selectedModel];
    const reasoningPresets = selectedReasoningCapability?.presets || {};
    const effectiveReasoning = {
        ...provider.reasoning,
        supported: Boolean(selectedReasoningCapability),
        available_presets: Object.keys(reasoningPresets),
        mapping_preview: reasoningPresets[editForm.reasoningPreset] || {},
    };

    return (
        <div id={`api-provider-card-${provider.id}`} className={styles.card}>
            <div className={styles.header}>
                <Text className={styles.title}>{provider.name}</Text>
                {provider.is_keyless && <Badge color="blue" variant="light" className={styles.statusBadge}>{t('api_key_no_required') || 'No Key Needed'}</Badge>}
                {!provider.is_keyless && provider.has_key && <Badge color="green" variant="light" className={styles.statusBadge}>{t('api_key_active')}</Badge>}
                {!provider.is_keyless && !provider.has_key && <Badge color="gray" variant="light" className={styles.statusBadge}>{t('api_key_not_configured')}</Badge>}
            </div>
            <Text className={styles.description}>{t(provider.description_key)}</Text>
            <div className={styles.actions}>
                {editing ? (
                    <Stack gap="sm">
                        <Divider label={t('settings_api_label_configuration')} labelPosition="center" />
                        {!provider.is_keyless && (
                            <PasswordInput
                                label={t('api_key_label', 'API Key')}
                                placeholder={t('api_key_placeholder')}
                                value={editForm.apiKey}
                                onChange={(event) => setEditForm({ ...editForm, apiKey: event.currentTarget.value })}
                                size="xs"
                                leftSection={<IconKey size={14} />}
                            />
                        )}
                        {canEditUrl && (
                            <>
                                <TextInput
                                    label={t('api_url_label', 'API Base URL')}
                                    placeholder={getApiUrlPlaceholder(provider.id)}
                                    value={editForm.apiUrl}
                                    onChange={(event) => setEditForm({ ...editForm, apiUrl: event.currentTarget.value })}
                                    error={apiUrlError}
                                    size="xs"
                                    leftSection={<IconServer size={14} />}
                                    rightSectionPointerEvents="auto"
                                    rightSection={(
                                        <Tooltip label={apiUrlHelp} multiline w={280} withArrow>
                                            <ActionIcon variant="subtle" size="sm" aria-label={t('api_url_help_label', 'API URL format help')}>
                                                <IconInfoCircle size={14} />
                                            </ActionIcon>
                                        </Tooltip>
                                    )}
                                />
                                {(isLocalOpenAIProvider || isOllamaProvider) && (
                                    <Button
                                        variant="light"
                                        size="xs"
                                        onClick={() => handleTestConnection(provider.id)}
                                        loading={testingConnection}
                                        disabled={!editForm.apiUrl.trim() || Boolean(apiUrlError)}
                                    >
                                        {t('api_test_connection')}
                                    </Button>
                                )}
                            </>
                        )}
                        <Select
                            label={t('api_model_select_label', 'Active Translation Model')}
                            placeholder={t('api_model_select_placeholder', 'Choose a model to use')}
                            description={t('api_model_select_description', 'Select which model will perform the translations')}
                            data={[...(provider.available_models || []), ...(editForm.models || []), ...(editForm.selectedModel ? [editForm.selectedModel] : [])]
                                .filter((value, index, values) => value && values.indexOf(value) === index)
                                .map((model) => ({ value: model, label: model }))}
                            value={editForm.selectedModel}
                            onChange={(value) => {
                                const capability = provider.reasoning_models?.[value];
                                const presets = Object.keys(capability?.presets || {});
                                setEditForm({
                                    ...editForm,
                                    selectedModel: value,
                                    reasoningBuiltinEnabled: capability ? editForm.reasoningBuiltinEnabled : false,
                                    reasoningPreset: presets.includes(editForm.reasoningPreset) ? editForm.reasoningPreset : (presets[0] || 'medium'),
                                });
                            }}
                            size="xs"
                            leftSection={<IconRobot size={14} />}
                            searchable
                            clearable
                        />
                        <TagsInput
                            label={t('api_models_label', 'Custom Models')}
                            placeholder={t('api_models_placeholder', 'Type and press Enter to add models')}
                            description={t('api_models_description', 'Models defined here will appear in the selector above')}
                            value={editForm.models}
                            onChange={(models) => {
                                const isAdded = models.length > editForm.models.length;
                                setEditForm((current) => ({ ...current, models, selectedModel: isAdded ? models[models.length - 1] : current.selectedModel }));
                            }}
                            size="xs"
                            leftSection={<IconRobot size={14} />}
                            clearable
                        />
                        <Divider label={t('api_prompt_controls_label', 'Prompt Controls')} labelPosition="center" />
                        <TextInput
                            label={t('api_prompt_prefix_label', 'User Prompt Prefix')}
                            placeholder="/no_think"
                            description={t('api_prompt_prefix_description', 'Prepended to every user prompt for this provider. Leave blank for model defaults.')}
                            value={editForm.promptPrefix}
                            onChange={(event) => setEditForm({ ...editForm, promptPrefix: event.currentTarget.value })}
                            size="xs"
                            leftSection={<IconMessage size={14} />}
                        />
                        <Textarea
                            label={t('api_system_prompt_suffix_label', 'System Prompt Suffix')}
                            placeholder="/no_think"
                            description={t('api_system_prompt_suffix_description', 'Appended to local provider system prompts. Useful for prompt-controlled thinking modes.')}
                            value={editForm.systemPromptSuffix}
                            onChange={(event) => setEditForm({ ...editForm, systemPromptSuffix: event.currentTarget.value })}
                            size="xs"
                            autosize
                            minRows={2}
                        />
                        <Divider label={t('api_reasoning_controls_label')} labelPosition="center" />
                        <ProviderReasoningSettings
                            reasoning={effectiveReasoning}
                            form={editForm}
                            onChange={(changes) => setEditForm((current) => ({ ...current, ...changes }))}
                        />
                        <Group grow mt="xs">
                            <Button size="xs" onClick={() => handleSave(provider.id)} loading={submitting} leftSection={<IconCheck size={14} />}>
                                {t('save')}
                            </Button>
                            <Button variant="subtle" color="gray" size="xs" onClick={handleCancelEdit} disabled={submitting}>
                                {t('cancel')}
                            </Button>
                        </Group>
                    </Stack>
                ) : (
                    <Stack gap="xs">
                        {!provider.is_keyless && (
                            <Group justify="space-between">
                                <Text size="xs" c="dimmed">{t('settings_api_label_key')}</Text>
                                <Text family="monospace" size="xs">{provider.has_key ? provider.masked_key : t('api_key_none_set')}</Text>
                            </Group>
                        )}
                        <Group justify="space-between">
                            <Text size="xs" c="dimmed">{t('settings_api_label_model')}</Text>
                            <Text size="xs" fw={500}>{provider.selected_model || 'N/A'}</Text>
                        </Group>
                        {provider.api_url && (
                            <Group justify="space-between">
                                <Text size="xs" c="dimmed">{t('settings_api_label_url')}</Text>
                                <Text size="xs" truncate style={{ maxWidth: '150px' }} title={provider.api_url}>{provider.api_url}</Text>
                            </Group>
                        )}
                        {provider.custom_models?.length > 0 && (
                            <Group justify="space-between">
                                <Text size="xs" c="dimmed">Models:</Text>
                                <Badge size="xs" variant="outline">{provider.custom_models.length} custom</Badge>
                            </Group>
                        )}
                        {(provider.prompt_prefix || provider.system_prompt_suffix) && (
                            <Group justify="space-between">
                                <Text size="xs" c="dimmed">{t('api_prompt_controls_label', 'Prompt Controls')}</Text>
                                <Badge size="xs" color="violet" variant="light">enabled</Badge>
                            </Group>
                        )}
                        <Button variant="light" size="xs" leftSection={<IconEdit size={14} />} onClick={() => handleEditClick(provider)} fullWidth mt="xs">
                            {t('settings_api_label_configure')}
                        </Button>
                    </Stack>
                )}
            </div>
        </div>
    );
};

export default BuiltInProviderCard;
