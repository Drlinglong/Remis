import React, { useState, useEffect, useCallback } from 'react';
import {
    Text,
    Group,
    Stack,
    Button,
    Loader,
    Accordion
} from '@mantine/core';
import {
    IconWorld, IconHome, IconBuildingSkyscraper
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';
import { normalizeArrayPayload } from '../utils/payload';
import styles from './ApiSettingsTab.module.css';
import ProviderReasoningSettings from './apiSettings/ProviderReasoningSettings';
import { parseCustomParameters } from './apiSettings/reasoningForm';
import ApiResourceGuides from './apiSettings/ApiResourceGuides';
import CustomProviderProfiles from './apiSettings/CustomProviderProfiles';
import BuiltInProviderCard from './apiSettings/BuiltInProviderCard';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';

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

const EMPTY_PROVIDER_FORM = {
    apiKey: '',
    models: [],
    apiUrl: '',
    selectedModel: '',
    promptPrefix: '',
    systemPromptSuffix: '',
    reasoningBuiltinEnabled: false,
    reasoningPreset: 'medium',
    customParametersText: ''
};

const LOCAL_OPENAI_PROVIDER_IDS = ['lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];
const CONCRETE_OPENAI_ENDPOINTS = ['/responses', '/chat/completions'];
const isConcreteOpenAIEndpoint = (providerId, apiUrl) => {
    if (!LOCAL_OPENAI_PROVIDER_IDS.includes(providerId) || !apiUrl) return false;
    const normalized = apiUrl.trim().replace(/\/+$/, '').toLowerCase();
    return CONCRETE_OPENAI_ENDPOINTS.some((endpoint) => normalized.endsWith(endpoint));
};

const ApiSettingsContent = () => {
    const { t } = useTranslation();
    const [providers, setProviders] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);

    // Edit form state
    const [editForm, setEditForm] = useState(EMPTY_PROVIDER_FORM);
    const [initialEditForm, setInitialEditForm] = useState(EMPTY_PROVIDER_FORM);
    const [profilesDirty, setProfilesDirty] = useState(false);
    const [discardToken, setDiscardToken] = useState(0);

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
        const nextForm = {
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
        };
        setEditingId(provider.id);
        setEditForm(nextForm);
        setInitialEditForm(nextForm);
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setEditForm(EMPTY_PROVIDER_FORM);
        setInitialEditForm(EMPTY_PROVIDER_FORM);
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
            setEditForm(EMPTY_PROVIDER_FORM);
            setInitialEditForm(EMPTY_PROVIDER_FORM);
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

    const discardChanges = useCallback(() => {
        setEditingId(null);
        setEditForm(EMPTY_PROVIDER_FORM);
        setInitialEditForm(EMPTY_PROVIDER_FORM);
        setProfilesDirty(false);
        setDiscardToken((current) => current + 1);
    }, []);
    const providerFormDirty = Boolean(
        editingId && JSON.stringify(editForm) !== JSON.stringify(initialEditForm),
    );
    useUnsavedChangesGuard({
        id: 'api-settings-provider-forms',
        isDirty: providerFormDirty || profilesDirty,
        onDiscard: discardChanges,
    });

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

    if (loading) {
        return <Loader size="sm" />;
    }

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
                                {groupDef.providers.map((providerId) => (
                                    <BuiltInProviderCard
                                        key={providerId}
                                        provider={providers.find((item) => item.id === providerId)}
                                        editing={editingId === providerId}
                                        editForm={editForm}
                                        submitting={submitting}
                                        testingConnection={testingConnection}
                                        t={t}
                                        setEditForm={setEditForm}
                                        handleSave={handleSave}
                                        handleCancelEdit={handleCancelEdit}
                                        handleEditClick={handleEditClick}
                                        handleTestConnection={handleTestConnection}
                                    />
                                ))}

                            </div>
                        </Accordion.Panel>
                    </Accordion.Item>
                ))}
            </Accordion>

            <CustomProviderProfiles
                onDirtyChange={setProfilesDirty}
                discardToken={discardToken}
            />
        </Stack>
    );
};

export default ApiSettingsContent;
