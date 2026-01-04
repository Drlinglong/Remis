import React, { useState, useEffect } from 'react';
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
    Alert,
    Anchor,
    List,
    Collapse,
    TagsInput,
    TextInput,
    Divider,
    Select,
    Accordion
} from '@mantine/core';
import {
    IconCheck, IconX, IconEdit, IconKey, IconInfoCircle, IconServer, IconRobot,
    IconWorld, IconHome, IconBuildingSkyscraper, IconSchool, IconAlertTriangle,
    IconBrandYoutube, IconBrandBilibili, IconChevronDown, IconChevronRight
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';
import styles from './ApiSettingsTab.module.css';

// Group Definitions
const PROVIDER_GROUPS = {
    usa: {
        title_key: 'api_group_usa',
        icon: <IconWorld size={20} />,
        providers: ['gemini', 'anthropic', 'openai', 'nvidia', 'grok', 'gemini_cli']
    },
    china: {
        title_key: 'api_group_china',
        icon: <IconBuildingSkyscraper size={20} />,
        providers: ['qwen', 'deepseek', 'kimi', 'minimax', 'zhipu', 'siliconflow', 'modelscope']
    },
    local: {
        title_key: 'api_group_local',
        icon: <IconHome size={20} />,
        providers: ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga']
    }
};

const GLOBAL_CUSTOM_PROVIDER_ID = 'your_favourite_api';


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
        selectedModel: ''
    });

    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        fetchProviders();
    }, []);

    const fetchProviders = async () => {
        try {
            const response = await api.get('/api/api-keys');
            setProviders(response.data);
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
    };

    const handleEditClick = (provider) => {
        setEditingId(provider.id);
        setEditForm({
            apiKey: '', // Always start empty for security
            models: provider.custom_models || [],
            apiUrl: provider.api_url || '',
            selectedModel: provider.selected_model || ''
        });
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setEditForm({ apiKey: '', models: [], apiUrl: '', selectedModel: '' });
    };

    const handleSave = async (providerId) => {
        setSubmitting(true);
        try {
            const payload = {
                provider_id: providerId,
                models: editForm.models,
                api_url: editForm.apiUrl,
                selected_model: editForm.selectedModel
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
        } catch (error) {
            console.error('Error updating API settings:', error);
            notifications.show({
                title: t('error'),
                message: error.response?.data?.detail || error.message,
                color: 'red'
            });
        } finally {
            setSubmitting(false);
        }
    };

    // Helper to render a single provider card
    const renderProviderCard = (provider) => {
        if (!provider) return null;

        const isEditing = editingId === provider.id;

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
                            {(provider.id === GLOBAL_CUSTOM_PROVIDER_ID || ['lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'ollama'].includes(provider.id)) && (
                                <TextInput
                                    label={t('api_url_label', 'API Base URL')}
                                    placeholder="http://localhost:1234/v1"
                                    value={editForm.apiUrl}
                                    onChange={(e) => setEditForm({ ...editForm, apiUrl: e.currentTarget.value })}
                                    size="xs"
                                    leftSection={<IconServer size={14} />}
                                />
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
                                onChange={(val) => setEditForm({ ...editForm, selectedModel: val })}
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

    const LinkButton = ({ url, children }) => (
        <Anchor
            component="button"
            type="button"
            onClick={async (e) => {
                e.preventDefault();
                console.log(`[LinkButton] Clicked: ${url}`);

                // Strategy: Try Tauri Shell Open FIRST. 
                // In Tauri v2, window.__TAURI__ is often not exposed by default, 
                // so we shouldn't rely on it for detection.
                try {
                    console.log('[LinkButton] Attempting to import @tauri-apps/plugin-shell...');
                    const { open } = await import('@tauri-apps/plugin-shell');

                    console.log('[LinkButton] Calling shell.open()...');
                    await open(url);
                    console.log('[LinkButton] Success: Shell open command sent.');
                } catch (err) {
                    // This creates a robust fallback for standard web browsers (Chrome/Edge)
                    // where the Tauri plugin might throw or fail to load.
                    console.warn('[LinkButton] Tauri shell failed or not available. Falling back to window.open.', err);
                    const newWindow = window.open(url, '_blank');
                    if (!newWindow) {
                        console.error('[LinkButton] window.open blocked!');
                        notifications.show({
                            title: t('error'),
                            message: 'Popup blocked. Please copy the link manually.',
                            color: 'red'
                        });
                    }
                }
            }}
            size="sm"
            style={{
                cursor: 'pointer',
                textAlign: 'left',
                // Mantine Anchor defaults are usually fine, but ensuring specific overrides if needed
            }}
        >
            {children}
        </Anchor>
    );

    return (
        <Stack gap="md">
            <Text c="dimmed" size="sm">
                {t('api_settings_description')}
            </Text>

            <Alert id="api-storage-info" variant="light" color="blue" title="API Configuration" icon={<IconInfoCircle />}>
                <Stack gap="xs">
                    <Text size="sm">{t('api_settings_storage_info')}</Text>
                    <Divider variant="dashed" />

                    <Group gap="xs">
                        <IconBrandBilibili size={16} />
                        <Text size="sm" fw={500}>Bilibili {t('api_guide_video_tutorial')}:</Text>
                    </Group>
                    <List size="sm" type="ordered" withPadding>
                        <List.Item>
                            <LinkButton url="https://www.bilibili.com/video/BV1LEKMexEV7/">
                                {t('api_guide_video_deepseek_title') || 'DeepSeek 技巧升级 2.0'}
                            </LinkButton>
                        </List.Item>
                        <List.Item>
                            <LinkButton url="https://www.bilibili.com/video/BV1FRuTzwEig/">
                                {t('api_guide_video_beginner_title') || '零基础 API 调用教程'}
                            </LinkButton>
                        </List.Item>
                    </List>

                    <Divider variant="dashed" />

                    <Group gap="xs">
                        <IconBrandYoutube size={16} />
                        <Text size="sm" fw={500}>YouTube {t('api_guide_video_tutorial')}:</Text>
                    </Group>
                    <List size="sm" type="ordered" withPadding>
                        <List.Item>
                            <LinkButton url="https://www.youtube.com/watch?v=OB99E7Y1cMA">
                                {t('api_guide_video_desc_1') || 'How to Get an OpenAI/ChatGPT API Key'}
                            </LinkButton>
                        </List.Item>
                        <List.Item>
                            <LinkButton url="https://www.youtube.com/watch?v=6BRyynZkvf0">
                                {t('api_guide_video_desc_2') || 'How To Get Your FREE Google Gemini API Key'}
                            </LinkButton>
                        </List.Item>
                    </List>

                    <Text size="xs" c="dimmed" mt="xs">
                        {t('api_guide_disclaimer')}
                    </Text>
                </Stack>
            </Alert>

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
