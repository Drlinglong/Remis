import React, { useState, useEffect, useCallback } from 'react';
import {
    Paper,
    Title,
    Text,
    Group,
    Stack,
    Button,
    PasswordInput,
    Badge,
    Loader,
    ActionIcon,
    Tooltip,
    Box,
    ThemeIcon,
    Collapse,
    TagsInput,
    TextInput,
    Textarea,
    Divider,
    Select,
    Accordion
} from '@mantine/core';
import {
    IconCheck, IconX, IconEdit, IconKey, IconInfoCircle, IconServer, IconRobot,
    IconWorld, IconHome, IconBuildingSkyscraper, IconSchool, IconAlertTriangle,
    IconChevronDown, IconChevronRight, IconMessage
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';
import { normalizeArrayPayload } from '../utils/payload';
import styles from './ApiSettingsTab.module.css';
import ProviderReasoningSettings from './apiSettings/ProviderReasoningSettings';
import { parseCustomParameters } from './apiSettings/reasoningForm';
import ApiResourceGuides from './apiSettings/ApiResourceGuides';

// Group Definitions
const PROVIDER_GROUPS = {
    usa: {
        title_key: 'api_group_usa',
        icon: <IconWorld size={20} />,
        providers: ['gemini', 'anthropic', 'openai', 'openrouter', 'nvidia', 'grok']
    },
    china: {
        title_key: 'api_group_china',
        icon: <IconBuildingSkyscraper size={20} />,
        providers: ['qwen', 'deepseek', 'kimi', 'minimax', 'zhipu', 'siliconflow', 'modelscope']
    },
    local: {
        title_key: 'api_group_local',
        icon: <IconHome size={20} />,
        providers: ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui']
    }
};

const GLOBAL_CUSTOM_PROVIDER_ID = 'your_favourite_api';
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


const ApiSettingsTab = () => {
    const { t } = useTranslation();
    const [providers, setProviders] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);

    // Edit form state
    const [editForm, setEditForm] = useState({
        apiKey: '',
        models: [],
        apiUrl: '',
        selectedModel: '',
        promptPrefix: '',
        systemPromptSuffix: '',
        reasoningBuiltinEnabled: false,
        reasoningPreset: 'medium',
        customParametersText: ''
    });

    const [submitting, setSubmitting] = useState(false);
    const [testingConnection, setTestingConnection] = useState(false);

    const fetchProviders = useCallback(async () => {
        try {
            const response = await api.get('/api/api-keys');
            setProviders(normalizeArrayPayload(response.data, ['providers', 'items', 'data', 'results']));
        } catch (error) {
            console.error('Error fetching API providers:', error);
            notifications.show({
                title: t('api_key_error_title'),
                message: t('api_key_error_fetch'),
                color: 'red'
            });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        fetchProviders();
    }, [fetchProviders]);

    const handleEditClick = (provider) => {
        setEditingId(provider.id);
        setEditForm({
            apiKey: '', // Always start empty for security
            models: provider.custom_models || [],
            apiUrl: provider.api_url || '',
            selectedModel: provider.selected_model || '',
            promptPrefix: provider.prompt_prefix || '',
            systemPromptSuffix: provider.system_prompt_suffix || '',
            reasoningBuiltinEnabled: Boolean(provider.reasoning?.supported && provider.reasoning?.builtin_enabled),
            reasoningPreset: provider.reasoning?.selected_preset || 'medium',
            customParametersText: Object.keys(provider.reasoning?.custom_parameters || {}).length
                ? JSON.stringify(provider.reasoning.custom_parameters, null, 2)
                : ''
        });
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setEditForm({ apiKey: '', models: [], apiUrl: '', selectedModel: '', promptPrefix: '', systemPromptSuffix: '', reasoningBuiltinEnabled: false, reasoningPreset: 'medium', customParametersText: '' });
    };

    const handleSave = async (providerId) => {
        if (isConcreteOpenAIEndpoint(providerId, editForm.apiUrl)) {
            notifications.show({
                title: t('error'),
                message: t('api_url_endpoint_error'),
                color: 'red'
            });
            return;
        }

        setSubmitting(true);
        try {
            const customParameters = parseCustomParameters(editForm.customParametersText);
            const payload = {
                provider_id: providerId,
                models: editForm.models,
                api_url: editForm.apiUrl,
                selected_model: editForm.selectedModel,
                prompt_prefix: editForm.promptPrefix,
                system_prompt_suffix: editForm.systemPromptSuffix,
                reasoning_builtin_enabled: editForm.reasoningBuiltinEnabled,
                reasoning_preset: editForm.reasoningPreset,
                custom_parameters: customParameters
            };

            if (editForm.apiKey.trim()) {
                payload.api_key = editForm.apiKey.trim();
            }

            await api.post('/api/providers/config', payload);

            notifications.show({
                title: t('success'),
                message: t('api_settings_saved', 'Settings saved successfully'),
                color: 'green'
            });
            setEditingId(null);
            fetchProviders(); // Refresh
        } catch (_error) {
            console.error('Error updating API settings:', _error);
            notifications.show({
                title: t('error'),
                message: _error.response?.data?.detail || _error.message,
                color: 'red'
            });
        } finally {
            setSubmitting(false);
        }
    };

    const handleTestConnection = async (providerId) => {
        if (isConcreteOpenAIEndpoint(providerId, editForm.apiUrl)) {
            notifications.show({ title: t('error'), message: t('api_url_endpoint_error'), color: 'red' });
            return;
        }

        setTestingConnection(true);
        try {
            await api.post('/api/providers/test-connection', {
                provider_id: providerId,
                api_url: editForm.apiUrl,
            });
            notifications.show({
                title: t('api_test_connection'),
                message: t('api_connection_success'),
                color: 'green',
            });
        } catch (error) {
            notifications.show({
                title: t('api_connection_failed'),
                message: error.response?.data?.detail || error.message,
                color: 'red',
            });
        } finally {
            setTestingConnection(false);
        }
    };

    // Helper to render a single provider card
    const renderProviderCard = (provider) => {
        if (!provider) return null;

        const isEditing = editingId === provider.id;
        const canEditUrl = provider.id === GLOBAL_CUSTOM_PROVIDER_ID || URL_EDITABLE_PROVIDER_IDS.includes(provider.id);
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
            <div key={provider.id} id={`api-provider-card-${provider.id}`} className={styles.card}>
                <div className={styles.header}>
                    <Text className={styles.title}>{provider.name}</Text>
                    {provider.is_keyless && (
                        <Badge color="blue" variant="light" className={styles.statusBadge}>{t('api_key_no_required') || 'No Key Needed'}</Badge>
                    )}
                    {!provider.is_keyless && provider.has_key && (
                        <Badge color="green" variant="light" className={styles.statusBadge}>{t('api_key_active')}</Badge>
                    )}
                    {!provider.is_keyless && !provider.has_key && (
                        <Badge color="gray" variant="light" className={styles.statusBadge}>{t('api_key_not_configured')}</Badge>
                    )}
                </div>

                <Text className={styles.description}>{t(provider.description_key)}</Text>

                <div className={styles.actions}>
                    {isEditing ? (
                        <Stack gap="sm">
                            <Divider label={t('settings_api_label_configuration')} labelPosition="center" />

                            {!provider.is_keyless && (
                                <PasswordInput
                                    label={t('api_key_label', 'API Key')}
                                    placeholder={t('api_key_placeholder')}
                                    value={editForm.apiKey}
                                    onChange={(e) => setEditForm({ ...editForm, apiKey: e.currentTarget.value })}
                                    size="xs"
                                    leftSection={<IconKey size={14} />}
                                />
                            )}

                            {/* Show URL edit for Custom OR Local models */}
                            {canEditUrl && (
                                <>
                                <TextInput
                                    label={t('api_url_label', 'API Base URL')}
                                    placeholder={getApiUrlPlaceholder(provider.id)}
                                    value={editForm.apiUrl}
                                    onChange={(e) => setEditForm({ ...editForm, apiUrl: e.currentTarget.value })}
                                    error={apiUrlError}
                                    size="xs"
                                    leftSection={<IconServer size={14} />}
                                    rightSectionPointerEvents="auto"
                                    rightSection={
                                        <Tooltip label={apiUrlHelp} multiline w={280} withArrow>
                                            <ActionIcon variant="subtle" size="sm" aria-label={t('api_url_help_label', 'API URL format help')}>
                                                <IconInfoCircle size={14} />
                                            </ActionIcon>
                                        </Tooltip>
                                    }
                                />
                                {LOCAL_OPENAI_PROVIDER_IDS.includes(provider.id) || isOllamaProvider ? (
                                    <Button
                                        variant="light"
                                        size="xs"
                                        onClick={() => handleTestConnection(provider.id)}
                                        loading={testingConnection}
                                        disabled={!editForm.apiUrl.trim() || Boolean(apiUrlError)}
                                    >
                                        {t('api_test_connection')}
                                    </Button>
                                ) : null}
                                </>
                            )}

                            <Select
                                label={t('api_model_select_label', 'Active Translation Model')}
                                placeholder={t('api_model_select_placeholder', 'Choose a model to use')}
                                description={t('api_model_select_description', 'Select which model will perform the translations')}
                                data={[
                                    ...(provider.available_models || []),
                                    ...(editForm.models || []),
                                    ...(editForm.selectedModel ? [editForm.selectedModel] : [])
                                ].filter((val, index, self) => val && self.indexOf(val) === index).map(m => ({ value: m, label: m }))}
                                value={editForm.selectedModel}
                                onChange={(val) => {
                                    const capability = provider.reasoning_models?.[val];
                                    const presets = Object.keys(capability?.presets || {});
                                    setEditForm({
                                        ...editForm,
                                        selectedModel: val,
                                        reasoningBuiltinEnabled: capability ? editForm.reasoningBuiltinEnabled : false,
                                        reasoningPreset: presets.includes(editForm.reasoningPreset)
                                            ? editForm.reasoningPreset
                                            : (presets[0] || 'medium'),
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
                                onChange={(val) => {
                                    const isAdded = val.length > editForm.models.length;
                                    setEditForm(prev => ({
                                        ...prev,
                                        models: val,
                                        selectedModel: isAdded ? val[val.length - 1] : prev.selectedModel
                                    }));
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
                                onChange={(e) => setEditForm({ ...editForm, promptPrefix: e.currentTarget.value })}
                                size="xs"
                                leftSection={<IconMessage size={14} />}
                            />

                            <Textarea
                                label={t('api_system_prompt_suffix_label', 'System Prompt Suffix')}
                                placeholder="/no_think"
                                description={t('api_system_prompt_suffix_description', 'Appended to local provider system prompts. Useful for prompt-controlled thinking modes.')}
                                value={editForm.systemPromptSuffix}
                                onChange={(e) => setEditForm({ ...editForm, systemPromptSuffix: e.currentTarget.value })}
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
                                <Button
                                    size="xs"
                                    onClick={() => handleSave(provider.id)}
                                    loading={submitting}
                                    leftSection={<IconCheck size={14} />}
                                >
                                    {t('save')}
                                </Button>
                                <Button
                                    variant="subtle"
                                    color="gray"
                                    size="xs"
                                    onClick={handleCancelEdit}
                                    disabled={submitting}
                                >
                                    {t('cancel')}
                                </Button>
                            </Group>
                        </Stack>
                    ) : (
                        <Stack gap="xs">
                            {!provider.is_keyless && (
                                <Group justify="space-between">
                                    <Text size="xs" c="dimmed">{t('settings_api_label_key')}</Text>
                                    <Text family="monospace" size="xs">
                                        {provider.has_key ? provider.masked_key : t('api_key_none_set')}
                                    </Text>
                                </Group>
                            )}

                            <Group justify="space-between">
                                <Text size="xs" c="dimmed">{t('settings_api_label_model')}</Text>
                                <Text size="xs" fw={500}>{provider.selected_model || 'N/A'}</Text>
                            </Group>

                            {provider.api_url && (
                                <Group justify="space-between">
                                    <Text size="xs" c="dimmed">{t('settings_api_label_url')}</Text>
                                    <Text size="xs" truncate style={{ maxWidth: '150px' }} title={provider.api_url}>
                                        {provider.api_url}
                                    </Text>
                                </Group>
                            )}

                            {provider.custom_models && provider.custom_models.length > 0 && (
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

                            <Button
                                variant="light"
                                size="xs"
                                leftSection={<IconEdit size={14} />}
                                onClick={() => handleEditClick(provider)}
                                fullWidth
                                mt="xs"
                            >
                                {t('settings_api_label_configure')}
                            </Button>
                        </Stack>
                    )}
                </div>
            </div>
        );
    };

    if (loading) {
        return <Loader size="sm" />;
    }

    // Identify the "Custom" provider object
    const customProvider = providers.find(p => p.id === GLOBAL_CUSTOM_PROVIDER_ID);

    return (
        <Stack data-remis-surface="surface" gap="md">
            <Text c="dimmed" size="sm">
                {t('api_settings_description')}
            </Text>

            <ApiResourceGuides />

            <Accordion id="api-providers-accordion" variant="separated" radius="md" multiple defaultValue={['usa', 'china', 'local']}>
                {Object.entries(PROVIDER_GROUPS).map(([groupKey, groupDef]) => (
                    <Accordion.Item key={groupKey} value={groupKey} className={styles.accordionItem}>
                        <Accordion.Control icon={groupDef.icon}>
                            <Text fw={500}>{t(groupDef.title_key)}</Text>
                        </Accordion.Control>
                        <Accordion.Panel>
                            <div className={styles.grid}>
                                {/* Render providers explicitly defined in this group */}
                                {groupDef.providers.map(providerId => {
                                    const provider = providers.find(p => p.id === providerId);
                                    return renderProviderCard(provider);
                                })}

                                {/* Special: Always render the "Custom API" card at the end of EACH group */}
                                {customProvider && (
                                    <div className={styles.customCardWrapper}>
                                        <div className={styles.customLabel}>
                                            <ThemeIcon size="xs" radius="xl" color="gray" variant="light"><IconEdit size={10} /></ThemeIcon>
                                            <Text size="xs" c="dimmed">Custom API (Global)</Text>
                                        </div>
                                        {renderProviderCard(customProvider)}
                                    </div>
                                )}
                            </div>
                        </Accordion.Panel>
                    </Accordion.Item>
                ))}
            </Accordion>
        </Stack>
    );
};

export default ApiSettingsTab;
