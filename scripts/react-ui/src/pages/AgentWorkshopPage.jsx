import React, { useState, useEffect } from 'react';
import { 
    Title, Text, Container, Paper, Button, Group, 
    Select, Table, Badge, ActionIcon, Stack, 
    Modal, Code, Divider, Alert, ScrollArea,
    LoadingOverlay, Box
} from '@mantine/core';
import { 
    IconScan, IconRobot, IconAlertTriangle, 
    IconCheck, IconRefresh, IconArrowRight,
    IconInfoCircle, IconBug, IconSearch, IconWand
} from '@tabler/icons-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import styles from './AgentWorkshop.module.css';

const AgentWorkshopPage = () => {
    const { t } = useTranslation();
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [issues, setIssues] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isCached, setIsCached] = useState(false);
    
    // Fix Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [currentIssue, setCurrentIssue] = useState(null);
    const [fixResult, setFixResult] = useState(null);
    const [fixing, setFixing] = useState(false);
    
    // Batch and Diff State
    const [batchSize, setBatchSize] = useState('5');
    const [fixedIssues, setFixedIssues] = useState([]);
    
    // LLM Selection State
    const [apiProviders, setApiProviders] = useState([]);
    const [selectedProvider, setSelectedProvider] = useState('');
    const [selectedModel, setSelectedModel] = useState('');

    useEffect(() => {
        fetchProjects();
        fetchApiConfig();
    }, []);

    useEffect(() => {
        if (selectedProject) {
            loadCached();
        } else {
            setIssues([]);
            setIsCached(false);
        }
    }, [selectedProject]);

    const fetchProjects = async () => {
        try {
            const res = await axios.get('/api/projects');
            const projectOptions = res.data.map(p => ({
                value: p.project_id || p.id,
                label: p.name
            }));
            setProjects(projectOptions);
        } catch (err) {
            console.error("Failed to fetch projects", err);
        }
    };

    const fetchApiConfig = async () => {
        try {
            const res = await axios.get('/api/locales/config');
            const data = res.data;
            if (data.api_providers) {
                setApiProviders(data.api_providers);
                if (data.api_providers.length > 0) {
                    setSelectedProvider(data.api_providers[0].value);
                    if (data.api_providers[0].models && data.api_providers[0].models.length > 0) {
                        setSelectedModel(data.api_providers[0].models[0]);
                    }
                }
            }
        } catch (err) {
            console.error("Failed to fetch API config", err);
        }
    };

    const loadCached = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`/api/agent-workshop/load-cached?project_id=${selectedProject}`);
            setIssues(res.data);
            setIsCached(res.data.length > 0);
        } catch (err) {
            console.error("Failed to load cached errors", err);
        } finally {
            setLoading(false);
        }
    };

    const handleScan = async () => {
        if (!selectedProject) return;
        setLoading(true);
        try {
            const res = await axios.get(`/api/agent-workshop/scan?project_id=${selectedProject}`);
            setIssues(res.data);
            setIsCached(false);
        } catch (err) {
            console.error("Scan failed", err);
        } finally {
            setLoading(false);
        }
    };

    const openFixModal = (issue) => {
        setCurrentIssue(issue);
        setFixResult(null);
        setIsModalOpen(true);
    };

    const handleFixRequest = async () => {
        if (!selectedProject || !currentIssue) return;
        setFixing(true);
        try {
            const res = await axios.post('/api/agent-workshop/fix', {
                project_id: selectedProject,
                api_provider: selectedProvider,
                api_model: selectedModel,
                ...currentIssue
            });
            
            if (res.data && res.data.status === 'SUCCESS') {
                setFixedIssues(prev => [{...currentIssue, suggested_fix: res.data.suggested_fix}, ...prev]);
                // Automatically remove it from the list if it's fixed
                setIssues(prev => prev.filter(i => i.key !== currentIssue.key || i.file_name !== currentIssue.file_name));
            }
            
            setFixResult(res.data);
        } catch (err) {
            console.error("Fix failed", err);
        } finally {
            setFixing(false);
        }
    };

    const applyFix = async () => {
        setIsModalOpen(false);
        setIssues(prev => prev.filter(i => i.key !== currentIssue.key || i.file_name !== currentIssue.file_name));
    };

    const handleFixAll = async () => {
        if (!selectedProject || issues.length === 0 || !selectedProvider) return;
        setFixing(true);
        
        const size = parseInt(batchSize, 10);
        let remainingIssues = [...issues];
        let newFixed = [];
        
        for (let i = 0; i < issues.length; i += size) {
            const batch = issues.slice(i, i + size);
            try {
                const res = await axios.post('/api/agent-workshop/fix-batch', {
                    project_id: selectedProject,
                    api_provider: selectedProvider,
                    api_model: selectedModel,
                    issues: batch
                });
                
                if (res.data && res.data.results) {
                    for (const r of res.data.results) {
                        if (r.status === 'SUCCESS') {
                            const originalIssue = batch.find(b => b.key === r.key && b.file_name === r.file_name);
                            if (originalIssue) {
                                newFixed.unshift({...originalIssue, suggested_fix: r.suggested_fix});
                            }
                            remainingIssues = remainingIssues.filter(iss => iss.key !== r.key || iss.file_name !== r.file_name);
                        }
                    }
                    // Update UI gracefully after each batch
                    setIssues([...remainingIssues]);
                    setFixedIssues(prev => [...newFixed, ...prev]);
                    newFixed = []; // reset for next batch
                }
            } catch (err) {
                console.error(`Batch fix failed`, err);
            }
        }
        
        setFixing(false);
    };

    return (
        <Box className={styles.container}>
            <Container size="xl" py="lg">
                <Stack gap="lg">
                    <Group justify="space-between">
                        <Stack gap={0}>
                            <Title order={2} className={styles.title}>
                                <IconRobot size={28} style={{ marginRight: 12, verticalAlign: 'middle' }} />
                                {t('page_title_agent_workshop')}
                            </Title>
                            <Text size="sm" c="dimmed">{t('agent_workshop.description')}</Text>
                        </Stack>
                    </Group>

                    <Paper p="md" radius="md" withBorder className={styles.glassPaper}>
                        <Group align="flex-end" grow>
                            <Select
                                label={t('agent_workshop.select_project')}
                                placeholder="Pick a project"
                                data={projects}
                                value={selectedProject}
                                onChange={setSelectedProject}
                            />
                            <Select
                                label={t('form_label_api_provider') || "LLM Provider"}
                                data={apiProviders}
                                value={selectedProvider}
                                onChange={(val) => {
                                    setSelectedProvider(val);
                                    const provider = apiProviders.find(p => p.value === val);
                                    if (provider && provider.models && provider.models.length > 0) {
                                        setSelectedModel(provider.models[0]);
                                    } else {
                                        setSelectedModel('');
                                    }
                                }}
                                disabled={fixing}
                            />
                            <Select
                                label={t('form_label_api_model') || "AI Model"}
                                data={apiProviders.find(p => p.value === selectedProvider)?.models || []}
                                value={selectedModel}
                                onChange={setSelectedModel}
                                disabled={fixing || !selectedProvider}
                                searchable
                                creatable
                                getCreateLabel={(query) => `+ Create ${query}`}
                            />
                            <Group>
                                <Button 
                                    leftSection={isCached ? <IconRefresh size={18} /> : <IconSearch size={18} />}
                                    onClick={handleScan}
                                    loading={loading}
                                    disabled={!selectedProject || fixing}
                                    variant={isCached ? "light" : "filled"}
                                >
                                    {isCached ? t('agent_workshop.rescan_btn') : t('agent_workshop.scan_btn')}
                                </Button>
                                {issues.length > 0 && (
                                    <Group spacing="xs">
                                        <Select
                                            value={batchSize}
                                            onChange={setBatchSize}
                                            data={['5', '10', '20', '50']}
                                            disabled={fixing}
                                            style={{ width: 80 }}
                                        />
                                        <Button
                                            color="indigo"
                                            leftSection={<IconWand size={18} />}
                                            onClick={handleFixAll}
                                            loading={fixing}
                                            disabled={!selectedProvider}
                                        >
                                            一键修复全部 (Fix All)
                                        </Button>
                                    </Group>
                                )}
                            </Group>
                        </Group>
                        {isCached && (
                            <Text size="xs" mt="xs" c="dimmed" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <IconInfoCircle size={12} />
                                Loaded from local sidecar (Last scan results)
                            </Text>
                        )}
                    </Paper>

                    {issues.length > 0 ? (
                        <Paper p="md" radius="md" withBorder className={styles.resultsPanel}>
                            <ScrollArea>
                                <Table verticalSpacing="sm">
                                    <Table.Thead>
                                        <Table.Tr>
                                            <Table.Th>{t('agent_workshop.table_file')}</Table.Th>
                                            <Table.Th style={{ width: 200 }}>
                                                <Group gap={4}>
                                                    {t('agent_workshop.table_error')}
                                                    <IconInfoCircle size={14} style={{ opacity: 0.6 }} />
                                                </Group>
                                            </Table.Th>
                                            <Table.Th>{t('agent_workshop.table_content')}</Table.Th>
                                            <Table.Th>{t('agent_workshop.table_action')}</Table.Th>
                                        </Table.Tr>
                                    </Table.Thead>
                                    <Table.Tbody>
                                        {issues.map((issue, idx) => (
                                            <Table.Tr key={idx}>
                                                <Table.Td>
                                                    <Text size="sm" fw={500}>{issue.file_name}</Text>
                                                    <Text size="xs" c="dimmed">{issue.key}</Text>
                                                </Table.Td>
                                                <Table.Td>
                                                    <Badge 
                                                        color="red" 
                                                        variant="light" 
                                                        size="sm"
                                                        style={{ 
                                                            height: 'auto', 
                                                            whiteSpace: 'normal', 
                                                            padding: '4px 8px',
                                                            textAlign: 'left',
                                                            lineHeight: 1.2,
                                                            display: 'block',
                                                            maxWidth: 180
                                                        }}
                                                    >
                                                        {issue.error_type}
                                                    </Badge>
                                                </Table.Td>
                                                <Table.Td>
                                                    <Stack gap={4}>
                                                        <Paper p="xs" withBorder bg="var(--mantine-color-dark-8)" style={{ maxWidth: 500 }}>
                                                            <code style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>
                                                                {issue.target_str}
                                                            </code>
                                                        </Paper>
                                                        <Text size="xs" c="dimmed">
                                                            {issue.details}
                                                        </Text>
                                                    </Stack>
                                                </Table.Td>
                                                <Table.Td>
                                                    <Button 
                                                        size="compact-xs" 
                                                        variant="light" 
                                                        leftSection={<IconWand size={14} />}
                                                        onClick={() => openFixModal(issue)}
                                                    >
                                                        {t('agent_workshop.fix_btn')}
                                                    </Button>
                                                </Table.Td>
                                            </Table.Tr>
                                        ))}
                                    </Table.Tbody>
                                </Table>
                            </ScrollArea>
                        </Paper>
                    ) : (
                        !loading && selectedProject && (
                            <Paper p="xl" radius="md" withBorder className={styles.emptyState} style={{ textAlign: 'center' }}>
                                <IconCheck size={48} color="green" style={{ opacity: 0.5 }} />
                                <Title order={3} mt="md">{t('agent_workshop.no_errors_title')}</Title>
                                <Text c="dimmed">{t('agent_workshop.no_errors_desc')}</Text>
                            </Paper>
                        )
                    )}
                </Stack>

                {/* Fix Modal */}
                <Modal
                    opened={isModalOpen}
                    onClose={() => setIsModalOpen(false)}
                    title={<Group gap="xs"><IconRobot size={20} /><Text fw={600}>{t('agent_workshop.modal_title')}</Text></Group>}
                    size="lg"
                >
                    <Box style={{ position: 'relative' }}>
                        <LoadingOverlay visible={fixing} overlayBlur={2} />
                        <Stack gap="md">
                            <Paper p="xs" withBorder>
                                <Text size="xs" fw={700} c="dimmed" tt="uppercase">{t('agent_workshop.modal_source_context')}</Text>
                                <Code block>{currentIssue?.source_str || "(No source context found)"}</Code>
                            </Paper>

                            <Paper p="xs" withBorder>
                                <Text size="xs" fw={700} c="red" tt="uppercase">{t('agent_workshop.modal_error_detected')}</Text>
                                <Code block color="red">{currentIssue?.target_str}</Code>
                                <Text size="xs" mt={4}>{currentIssue?.details}</Text>
                            </Paper>

                            {!fixResult && (
                                <Button 
                                    fullWidth 
                                    variant="gradient" 
                                    gradient={{ from: 'indigo', to: 'cyan' }}
                                    onClick={handleFixRequest}
                                    disabled={fixing || !selectedProvider}
                                >
                                    {selectedProvider ? t('agent_workshop.fix_btn') : '请先在上方选择模型'}
                                </Button>
                            )}

                            {fixResult && (
                                <Stack gap="md">
                                    <Alert icon={<IconInfoCircle size={16} />} title={t('agent_workshop.modal_analysis')} color="indigo" variant="light">
                                        <Text size="sm" fs="italic">{fixResult.reflection}</Text>
                                    </Alert>

                                    <Paper p="xs" withBorder style={{ backgroundColor: 'rgba(40, 167, 69, 0.05)' }}>
                                        <Text size="xs" fw={700} c="green" tt="uppercase">{t('agent_workshop.modal_suggestion')}</Text>
                                        <Code block color="green">{fixResult.suggested_fix}</Code>
                                        {fixResult.parity_message && (
                                            <Text size="xs" mt={4} c={fixResult.status === 'SUCCESS' ? 'green' : 'orange'}>
                                                <IconCheck size={12} /> {fixResult.parity_message}
                                            </Text>
                                        )}
                                    </Paper>

                                    <Group grow mt="lg">
                                        <Button variant="subtle" onClick={() => setFixResult(null)}>{t('agent_workshop.regenerate')}</Button>
                                        <Button color="green" onClick={applyFix}>{t('agent_workshop.apply_fix')}</Button>
                                    </Group>
                                </Stack>
                            )}
                        </Stack>
                    </Box>
                </Modal>
                
                {fixedIssues.length > 0 && (
                    <Paper mt="xl" p="md" radius="md" withBorder className={styles.glassPaper}>
                        <Title order={4} mb="md">近期已修复 (Recently Fixed) - {fixedIssues.length}</Title>
                        <ScrollArea h={400}>
                            {fixedIssues.map((item, idx) => (
                                <Paper key={idx} p="sm" mb="sm" withBorder shadow="sm">
                                    <Group position="apart" mb="xs">
                                        <Text size="sm" fw={600} color="dimmed">{item.file_name}</Text>
                                        <Text size="xs" color="dimmed">Key: {item.key}</Text>
                                    </Group>
                                    <Code block color="red" mb="xs" style={{ textDecoration: 'line-through' }}>
                                        - {item.target_str}
                                    </Code>
                                    <Code block color="teal">
                                        + {item.suggested_fix}
                                    </Code>
                                </Paper>
                            ))}
                        </ScrollArea>
                    </Paper>
                )}
            </Container>
        </Box>
    );
};

export default AgentWorkshopPage;
