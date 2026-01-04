import React, { useState, useEffect } from 'react';
import { Container, Title, Text, Paper, Group, Badge, Button, ScrollArea, Box, LoadingOverlay } from '@mantine/core';
import { IconArchive, IconArrowLeft, IconRefresh } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';

const API_BASE = '/api';

export default function ArchivesPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchArchivedProjects = async () => {
    setLoading(true);
    try {
      const res = await api.get(`${API_BASE}/projects/archives`);
      setProjects(res.data);
    } catch (error) {
      console.error("Failed to load archived projects", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArchivedProjects();
  }, []);

  const handleRestoreProject = async (projectId) => {
    try {
      await api.put(`${API_BASE}/project/${projectId}/status`, { status: 'active' });
      fetchArchivedProjects(); // Refresh the list
    } catch (error) {
      console.error("Failed to restore project", error);
      alert(`Failed to restore project: ${error.response?.data?.detail || error.message}`);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'archived':
        return 'yellow';
      case 'deleted':
        return 'red';
      default:
        return 'gray';
    }
  };

  return (
    <Container fluid p="md" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" onClick={() => navigate('/projects')} leftSection={<IconArrowLeft size={16} />}>
            Back to Projects
          </Button>
          <Title order={2}>
            <Group>
              <IconArchive />
              Archives
            </Group>
          </Title>
        </Group>
        <Button onClick={fetchArchivedProjects} variant="light" leftSection={<IconRefresh size={16} />}>
          Refresh
        </Button>
      </Group>

      <Text c="dimmed" mb="xl">
        Here you can find projects that are archived or in the recycle bin.
      </Text>

      <Box style={{ position: 'relative', flex: 1 }}>
        <LoadingOverlay visible={loading} overlayProps={{ radius: "sm", blur: 2 }} />
        <ScrollArea style={{ height: '100%' }}>
          {projects.length === 0 && !loading ? (
            <Text c="dimmed" fs="italic" ta="center" mt="xl">
              The archives are empty.
            </Text>
          ) : (
            <Paper>
              {projects.map((p) => (
                <Paper key={p.project_id} p="md" withBorder mb="sm" radius="md">
                  <Group justify="space-between">
                    <Box>
                      <Text fw={600} size="lg">{p.name}</Text>
                      <Text size="xs" c="dimmed">{p.game_id} • {p.source_path}</Text>
                      {p.notes && <Text size="sm" mt="xs">Notes: {p.notes}</Text>}
                    </Box>
                    <Group>
                      <Badge color={getStatusColor(p.status)}>{p.status}</Badge>
                      <Button
                        variant="light"
                        color="green"
                        size="xs"
                        onClick={() => handleRestoreProject(p.project_id)}
                      >
                        Restore
                      </Button>
                    </Group>
                  </Group>
                </Paper>
              ))}
            </Paper>
          )}
        </ScrollArea>
      </Box>
    </Container>
  );
}
