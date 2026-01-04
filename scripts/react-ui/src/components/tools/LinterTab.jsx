import React, { useState } from 'react';
import {
    Container,
    Paper,
    Title,
    Text,
    Textarea,
    Button,
    Group,
    Stack,
    Alert,
    Table,
    Badge,
    Select,
    Loader
} from '@mantine/core';
import { IconCheck, IconAlertTriangle, IconInfoCircle, IconX } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import api from '../../utils/api';
import layoutStyles from '../layout/Layout.module.css';

const LinterTab = () => {
    const { t } = useTranslation();
    const [content, setContent] = useState('');
    const [gameId, setGameId] = useState('1'); // Default to Victoria 3 (ID: 1)
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleValidate = async () => {
        if (!content.trim()) return;

        setLoading(true);
        setError(null);
        setResults([]);

        try {
            const response = await api.post('/api/validate/localization', {
                game_id: gameId,
                content: content,
                source_lang_code: 'en_US' // Hardcoded for now, could be selectable
            });
            setResults(response.data);
        } catch (err) {
            console.error("Validation failed:", err);
            setError("Failed to validate content. Please check the backend connection.");
        } finally {
            setLoading(false);
        }
    };

    const getLevelColor = (level) => {
        switch (level) {
            case 'error': return 'red';
            case 'warning': return 'yellow';
            case 'info': return 'blue';
            default: return 'gray';
        }
    };

    const getLevelIcon = (level) => {
        switch (level) {
            case 'error': return <IconX size={16} />;
            case 'warning': return <IconAlertTriangle size={16} />;
            case 'info': return <IconInfoCircle size={16} />;
            default: return null;
        }
    };

    return (
        <Container size="xl" py="md">
            <Paper withBorder p="md" radius="md" className={layoutStyles.glassCard}>
                <Stack gap="md">
                    <Group justify="space-between">
                        <Title order={3}>Localization Linter</Title>
                        <Select
                            label="Game Profile"
                            placeholder="Select game"
                            data={[
                                { value: '1', label: 'Victoria 3' },
                                { value: '2', label: 'Stellaris' },
                                { value: '3', label: 'Europa Universalis IV' },
                                { value: '4', label: 'Hearts of Iron IV' },
                                { value: '5', label: 'Crusader Kings III' },
                            ]}
                            value={gameId}
                            onChange={setGameId}
                            style={{ width: 200 }}
                        />
                    </Group>

                    <Text c="dimmed" size="sm">
                        Paste your localization YAML content below to check for syntax errors and formatting issues.
                    </Text>

                    <Textarea
                        placeholder={'l_english:\\n  key:0 "Value"'}
                        minRows={10}
                        maxRows={20}
                        value={content}
                        onChange={(event) => setContent(event.currentTarget.value)}
                        styles={{ input: { fontFamily: 'monospace' } }}
                    />

                    <Group justify="flex-end">
                        <Button
                            onClick={handleValidate}
                            loading={loading}
                            leftSection={<IconCheck size={16} />}
                        >
                            Validate
                        </Button>
                    </Group>

                    {error && (
                        <Alert icon={<IconX size={16} />} title="Error" color="red">
                            {error}
                        </Alert>
                    )}

                    {results.length > 0 && (
                        <Table striped highlightOnHover>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Line</Table.Th>
                                    <Table.Th>Level</Table.Th>
                                    <Table.Th>Key</Table.Th>
                                    <Table.Th>Message</Table.Th>
                                    <Table.Th>Details</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {results.map((result, index) => (
                                    <Table.Tr key={index}>
                                        <Table.Td>{result.line_number}</Table.Td>
                                        <Table.Td>
                                            <Badge color={getLevelColor(result.level)} leftSection={getLevelIcon(result.level)}>
                                                {result.level.toUpperCase()}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td style={{ fontFamily: 'monospace' }}>{result.key || '-'}</Table.Td>
                                        <Table.Td>{result.message}</Table.Td>
                                        <Table.Td>{result.details}</Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    )}

                    {results.length === 0 && !loading && content.trim() && !error && (
                        <Text c="dimmed" ta="center" fs="italic">No issues found or validation not run yet.</Text>
                    )}
                </Stack>
            </Paper>
        </Container>
    );
};

export default LinterTab;
