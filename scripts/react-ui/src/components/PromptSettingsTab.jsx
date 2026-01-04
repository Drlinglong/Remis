import React, { useState, useEffect } from 'react';
import {
    Stack,
    Title,
    Text,
    Select,
    Textarea,
    Button,
    Group,
    Paper,
    Divider,
    Alert,
    Modal,
    Loader,
    ActionIcon,
    Tooltip,
    Grid,
    Badge,
    Collapse,
    Box
} from '@mantine/core';
import {
    IconDeviceFloppy,
    IconRefresh,
    IconAlertTriangle,
    IconInfoCircle,
    IconMaximize,
    IconMinimize
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';

// Internal Component: Expandable Textarea
const ExpandableTextarea = ({ label, value, onChange, readOnly, placeholder, minRows = 4, maxRows = 30, rightSection }) => {
    const [expanded, setExpanded] = useState(false);

    return (
        <Box>
            <Group justify="space-between" mb={4}>
                <Text size="sm" fw={500}>{label}</Text>
                <Group gap="xs">
                    {rightSection}
                    <Button
                        size="compact-xs"
                        variant="subtle"
                        color="gray"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setExpanded(!expanded);
                        }}
                        leftSection={expanded ? <IconMinimize size={14} /> : <IconMaximize size={14} />}
                    >
                        {expanded ? "Collapse" : "Expand"}
                    </Button>
                </Group>
            </Group>
            <Textarea
                placeholder={placeholder}
                value={value}
                onChange={onChange}
                readOnly={readOnly}
                minRows={expanded ? 25 : minRows}
                maxRows={expanded ? 50 : maxRows}
                styles={{
                    input: {
                        fontFamily: 'monospace',
                        fontSize: '12px',
                        transition: 'all 0.2s ease',
                        minHeight: expanded ? '600px' : undefined
                    }
                }}
            />
        </Box>
    );
};

const PromptSettingsTab = () => {
    const { t } = useTranslation();
    const [loading, setLoading] = useState(true);
    const [promptsData, setPromptsData] = useState(null);
    const [selectedGameId, setSelectedGameId] = useState(null);

    // Form states
    const [currentSystemPrompt, setCurrentSystemPrompt] = useState('');
    const [currentFormatPrompt, setCurrentFormatPrompt] = useState('');
    const [customGlobalPrompt, setCustomGlobalPrompt] = useState('');

    // UI states
    const [submittingSystem, setSubmittingSystem] = useState(false);
    const [submittingFormat, setSubmittingFormat] = useState(false);
    const [submittingCustom, setSubmittingCustom] = useState(false);
    const [resetModalOpen, setResetModalOpen] = useState(false);
    const [resetTarget, setResetTarget] = useState(null); // 'system', 'format', 'custom'

    // Helpers
    const variables = [
        { label: '{source_lang_name}', desc: 'Source Language Name' },
        { label: '{target_lang_name}', desc: 'Target Language Name' },
        { label: '{mod_name}', desc: 'Mod Name' },
        { label: '{task_description}', desc: 'Task Description' },
    ];

    useEffect(() => {
        fetchPrompts();
    }, []);

    useEffect(() => {
        if (promptsData && selectedGameId) {
            const gameData = promptsData.system_prompts[selectedGameId];
            if (gameData) {
                setCurrentSystemPrompt(gameData.current);
                setCurrentFormatPrompt(gameData.format_current);
            }
        }
    }, [selectedGameId, promptsData]);

    const fetchPrompts = async () => {
        try {
            const response = await api.get('/api/prompts');
            setPromptsData(response.data);
            setCustomGlobalPrompt(response.data.custom_global_prompt || '');

            // Select first game by default if not selected
            if (!selectedGameId && response.data.system_prompts) {
                const firstGame = Object.keys(response.data.system_prompts)[0];
                if (firstGame) setSelectedGameId(firstGame);
            }
        } catch (error) {
            console.error("Failed to fetch prompts:", error);
            notifications.show({
                title: t('error'),
                message: t('prompt_fetch_error', 'Failed to load prompts'),
                color: 'red'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleSaveSystemPrompt = async () => {
        if (!selectedGameId) return;
        setSubmittingSystem(true);
        try {
            await api.post('/api/prompts/system', {
                game_id: selectedGameId,
                prompt_template: currentSystemPrompt
            });
            notifications.show({
                title: t('success'),
                message: t('prompt_save_success', 'System prompt saved successfully'),
                color: 'green'
            });
            fetchPrompts();
        } catch (error) {
            console.error("Failed to save system prompt:", error);
            notifications.show({
                title: t('error'),
                message: t('prompt_save_error', 'Failed to save system prompt'),
                color: 'red'
            });
        } finally {
            setSubmittingSystem(false);
        }
    };

    const handleSaveFormatPrompt = async () => {
        if (!selectedGameId) return;
        setSubmittingFormat(true);
        try {
            await api.post('/api/prompts/format', {
                game_id: selectedGameId,
                format_prompt: currentFormatPrompt
            });
            notifications.show({
                title: t('success'),
                message: t('prompt_save_success', 'Format prompt saved successfully'),
                color: 'green'
            });
            fetchPrompts();
        } catch (error) {
            console.error("Failed to save format prompt:", error);
            notifications.show({
                title: t('error'),
                message: t('prompt_save_error', 'Failed to save format prompt'),
                color: 'red'
            });
        } finally {
            setSubmittingFormat(false);
        }
    };

    const handleSaveCustomPrompt = async () => {
        setSubmittingCustom(true);
        try {
            await api.post('/api/prompts/custom', {
                custom_prompt: customGlobalPrompt
            });
            notifications.show({
                title: t('success'),
                message: t('prompt_save_success', 'Custom prompt saved successfully'),
                color: 'green'
            });
        } catch (error) {
            console.error("Failed to save custom prompt:", error);
            notifications.show({
                title: t('error'),
                message: t('prompt_save_error', 'Failed to save custom prompt'),
                color: 'red'
            });
        } finally {
            setSubmittingCustom(false);
        }
    };

    const handleResetClick = (target) => {
        setResetTarget(target);
        setResetModalOpen(true);
    };

    const confirmReset = async () => {
        setResetModalOpen(false);
        try {
            const payload = {
                game_id: ['system', 'format'].includes(resetTarget) ? selectedGameId : null,
                reset_custom: resetTarget === 'custom',
                reset_format: resetTarget === 'format'
            };

            await api.post('/api/prompts/reset', payload);

            notifications.show({
                title: t('success'),
                message: t('prompt_reset_success', 'Prompt reset to default'),
                color: 'green'
            });
            fetchPrompts();
        } catch (error) {
            console.error("Failed to reset prompt:", error);
            notifications.show({
                title: t('error'),
                message: t('prompt_reset_error', 'Failed to reset prompt'),
                color: 'red'
            });
        }
    };

    const insertVariable = (variable, setter, currentValue) => {
        setter(currentValue + variable);
    };

    if (loading) return <Loader />;

    const gameOptions = promptsData?.system_prompts
        ? Object.entries(promptsData.system_prompts).map(([id, data]) => ({
            value: id,
            label: data.name
        }))
        : [];

    const selectedGameData = selectedGameId && promptsData?.system_prompts
        ? promptsData.system_prompts[selectedGameId]
        : null;

    return (
        <Stack gap="xl">
            {/* --- Warnings --- */}
            <Alert variant="light" color="orange" title={t('prompt_settings_warning_title')} icon={<IconAlertTriangle />}>
                {t('prompt_settings_warning_desc')}
            </Alert>

            {/* --- Game Selector --- */}
            <Group>
                <Select
                    label={t('select_game_profile', 'Select Game Profile')}
                    data={gameOptions}
                    value={selectedGameId}
                    onChange={setSelectedGameId}
                    allowDeselect={false}
                    searchable
                    style={{ flexGrow: 1 }}
                />
            </Group>

            {selectedGameData && (
                <Grid gutter="xl">
                    {/* --- LEFT COLUMN: System Prompt --- */}
                    <Grid.Col span={6}>
                        <Paper p="md" withBorder h="100%">
                            <Stack h="100%">
                                <Title order={4}>{t('prompt_settings_system_title', 'System Prompt (Role & Context)')}</Title>
                                <Text size="sm" c="dimmed">{t('prompt_settings_system_desc')}</Text>

                                <Group justify="space-between" align="center">
                                    <Group gap="xs">
                                        <Text size="sm" fw={600}>{t('current_prompt', 'Current Prompt')}</Text>
                                        {selectedGameData.is_overridden && (
                                            <Badge color="orange" variant="light">{t('overridden', 'Overridden')}</Badge>
                                        )}
                                    </Group>
                                    <Group gap="xs">
                                        <Tooltip label={selectedGameData.is_overridden ? t('reset_desc', 'Reset to default') : t('reset_disabled_desc', 'No override to reset')}>
                                            <span style={{ display: 'inline-block' }}> {/* Wrapper for disabled button tooltip */}
                                                <Button
                                                    variant="subtle" color="red" size="xs"
                                                    onClick={() => handleResetClick('system')}
                                                    disabled={!selectedGameData.is_overridden}
                                                    style={{ pointerEvents: !selectedGameData.is_overridden ? 'none' : 'auto' }} // Ensure click is blocked if disabled but tooltip works on wrapper
                                                >
                                                    {t('reset')}
                                                </Button>
                                            </span>
                                        </Tooltip>
                                        <Button
                                            leftSection={<IconDeviceFloppy size={14} />}
                                            size="xs"
                                            onClick={handleSaveSystemPrompt}
                                            loading={submittingSystem}
                                        >
                                            {t('save')}
                                        </Button>
                                    </Group>
                                </Group>

                                <Group gap={5}>
                                    {variables.map(v => (
                                        <Tooltip label={v.desc} key={v.label}>
                                            <Badge
                                                variant="outline"
                                                style={{ cursor: 'pointer' }}
                                                onClick={() => insertVariable(v.label, setCurrentSystemPrompt, currentSystemPrompt)}
                                            >
                                                {v.label}
                                            </Badge>
                                        </Tooltip>
                                    ))}
                                </Group>

                                <ExpandableTextarea
                                    value={currentSystemPrompt}
                                    onChange={(e) => setCurrentSystemPrompt(e.currentTarget.value)}
                                    minRows={4}
                                />

                                <Divider label={t('default_system_prompt')} labelPosition="center" />

                                <ExpandableTextarea
                                    value={selectedGameData.default}
                                    readOnly={true}
                                    minRows={4}
                                />
                            </Stack>
                        </Paper>
                    </Grid.Col>

                    {/* --- RIGHT COLUMN: Format Prompt --- */}
                    <Grid.Col span={6}>
                        <Paper p="md" withBorder h="100%">
                            <Stack h="100%">
                                <Title order={4}>{t('prompt_formatting_rules', 'Formatting Rules (JSON Structure)')}</Title>
                                <Text size="sm" c="dimmed">
                                    {t('prompt_formatting_desc')}
                                </Text>

                                <Group justify="space-between" align="center">
                                    <Group gap="xs">
                                        <Text size="sm" fw={600}>{t('current_rules', 'Current Rules')}</Text>
                                        {selectedGameData.is_format_overridden && (
                                            <Badge color="orange" variant="light">{t('overridden', 'Overridden')}</Badge>
                                        )}
                                    </Group>
                                    <Group gap="xs">
                                        <Tooltip label={selectedGameData.is_format_overridden ? t('reset_desc', 'Reset to default') : t('reset_disabled_desc', 'No override to reset')}>
                                            <span style={{ display: 'inline-block' }}>
                                                <Button
                                                    variant="subtle" color="red" size="xs"
                                                    onClick={() => handleResetClick('format')}
                                                    disabled={!selectedGameData.is_format_overridden}
                                                    style={{ pointerEvents: !selectedGameData.is_format_overridden ? 'none' : 'auto' }}
                                                >
                                                    {t('reset')}
                                                </Button>
                                            </span>
                                        </Tooltip>
                                        <Button
                                            leftSection={<IconDeviceFloppy size={14} />}
                                            size="xs"
                                            onClick={handleSaveFormatPrompt}
                                            loading={submittingFormat}
                                        >
                                            {t('save')}
                                        </Button>
                                    </Group>
                                </Group>

                                {/* Common format variables */}
                                <Group gap={5}>
                                    <Tooltip label="Input chunk size">
                                        <Badge
                                            variant="outline" color="gray"
                                            style={{ cursor: 'pointer' }}
                                            onClick={() => insertVariable('{chunk_size}', setCurrentFormatPrompt, currentFormatPrompt)}
                                        >
                                            {'{chunk_size}'}
                                        </Badge>
                                    </Tooltip>
                                    <Tooltip label="Input list content">
                                        <Badge
                                            variant="outline" color="gray"
                                            style={{ cursor: 'pointer' }}
                                            onClick={() => insertVariable('{numbered_list}', setCurrentFormatPrompt, currentFormatPrompt)}
                                        >
                                            {'{numbered_list}'}
                                        </Badge>
                                    </Tooltip>
                                </Group>

                                <ExpandableTextarea
                                    value={currentFormatPrompt}
                                    onChange={(e) => setCurrentFormatPrompt(e.currentTarget.value)}
                                    minRows={4}
                                />

                                <Divider label={t('default_format_rules')} labelPosition="center" />

                                <ExpandableTextarea
                                    value={selectedGameData.format_default}
                                    readOnly={true}
                                    minRows={4}
                                />
                            </Stack>
                        </Paper>
                    </Grid.Col>
                </Grid>
            )}

            {/* --- Custom Global Prompt Section (Full Width) --- */}
            <Paper p="md" withBorder mt="xl">
                <Title order={4} mb="sm">{t('prompt_settings_custom_title', 'Persistent Custom Prompt')}</Title>
                <Alert icon={<IconInfoCircle size={16} />} color="green" variant="light" mb="md">
                    {t('prompt_settings_custom_desc', 'This prompt will be automatically pre-filled into the "Additional Prompt" field for every new translation task.')}
                </Alert>

                <Group justify="flex-end" mb="xs">
                    <Button
                        variant="subtle"
                        color="red"
                        onClick={() => handleResetClick('custom')}
                        disabled={!customGlobalPrompt}
                        leftSection={<IconRefresh size={16} />}
                        size="xs"
                    >
                        {t('prompt_clear', 'Clear')}
                    </Button>
                    <Button
                        leftSection={<IconDeviceFloppy size={16} />}
                        onClick={handleSaveCustomPrompt}
                        loading={submittingCustom}
                        size="xs"
                    >
                        {t('prompt_save_custom', 'Save')}
                    </Button>
                </Group>

                <ExpandableTextarea
                    placeholder={t('prompt_custom_placeholder')}
                    value={customGlobalPrompt}
                    onChange={(e) => setCustomGlobalPrompt(e.currentTarget.value)}
                    minRows={4}
                />
            </Paper>

            {/* --- Reset Confirmation Modal --- */}
            <Modal
                opened={resetModalOpen}
                onClose={() => setResetModalOpen(false)}
                title={<Group><IconAlertTriangle color="red" /><Text fw={700}>{t('prompt_reset_confirm_title', 'Confirm Reset')}</Text></Group>}
                centered
            >
                <Text mb="lg">
                    {t('prompt_reset_confirm_message', 'This will revert your changes to the default system settings. This action cannot be undone. Are you sure?')}
                </Text>
                <Group justify="flex-end">
                    <Button variant="default" onClick={() => setResetModalOpen(false)}>{t('cancel')}</Button>
                    <Button color="red" onClick={confirmReset}>{t('confirm_reset', 'Yes, Reset')}</Button>
                </Group>
            </Modal>
        </Stack>
    );
};

export default PromptSettingsTab;
