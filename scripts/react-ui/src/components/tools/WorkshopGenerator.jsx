import React, { useState, useEffect } from 'react';
import {
  Radio,
  Select,
  TextInput,
  Textarea,
  Button,
  LoadingOverlay,
  Title,
  Text,
  Group,
  Alert,
  Autocomplete,
  CopyButton,
  ActionIcon,
  Tooltip
} from '@mantine/core';
import { IconCopy, IconAlertCircle } from '@tabler/icons-react';
import api from '../../utils/api';
import { useTranslation } from 'react-i18next';
import { notifications } from '@mantine/notifications';

const WorkshopGenerator = () => {
  const { t } = useTranslation();

  // --- State Management ---
  const [projects, setProjects] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [apiProviders, setApiProviders] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [manualItemId, setManualItemId] = useState('');
  const [inputMode, setInputMode] = useState('project');
  const [userTemplate, setUserTemplate] = useState(
    `<!-- Chinese Title -->\n[h1]在此输入您的中文标题[/h1]\n\n<!-- Chinese Description -->\n[b]在此输入您的中文简介和描述。[/b]\n\n`
  );
  const [targetLanguage, setTargetLanguage] = useState('zh');
  const [customLanguage, setCustomLanguage] = useState('');
  const [generatedBbcode, setGeneratedBbcode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');

  // --- Data Fetching ---
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [projectsResponse, configResponse] = await Promise.all([
          api.get('/api/projects'),
          api.get('/api/config')
        ]);

        const projectData = projectsResponse.data;
        setProjects(projectData);
        if (projectData.length > 0) {
          setSelectedProjectId(projectData[0].project_id);
        }

        const configData = configResponse.data;
        if (configData.languages) {
          const langArray = Object.values(configData.languages);
          setLanguages(langArray);
        }
        if (configData.api_providers) {
          setApiProviders(configData.api_providers);
          if (configData.api_providers.length > 0) {
            setSelectedProvider(configData.api_providers[0].value);
          }
        }

      } catch (err) {
        const fetchError = t('workshop_generator.errors.fetch_config_failed');
        setError(fetchError);
        notifications.show({ title: 'Error', message: fetchError, color: 'red' });
      }
    };
    fetchData();
  }, [t]);

  // --- Helper Functions ---
  const extractWorkshopId = (value) => {
    if (!value) return '';
    const match = value.match(/(?:steamcommunity\.com\/sharedfiles\/filedetails\/\?id=)(\d+)/);
    return match ? match[1] : value;
  };

  const handleManualIdChange = (value) => {
    const extractedId = extractWorkshopId(value);
    setManualItemId(extractedId);
  };

  // --- Core Logic Handler ---
  const handleGenerate = async () => {
    setError(null);
    setSuccessMessage('');
    setIsLoading(true);
    setGeneratedBbcode('');

    let finalItemId = '';
    let finalProjectId = '';

    if (inputMode === 'project') {
      const selectedProject = projects.find(p => p.project_id === selectedProjectId);
      if (!selectedProject) {
        setError(t('workshop_generator.errors.project_not_selected'));
        setIsLoading(false);
        return;
      }
      if (!selectedProject.workshop_id) {
        setError(t('workshop_generator.errors.project_id_missing'));
        setIsLoading(false);
        return;
      }
      finalItemId = selectedProject.workshop_id;
      finalProjectId = selectedProject.project_id;
    } else {
      finalItemId = manualItemId;
    }

    if (!finalItemId || !selectedProvider) {
      setError(t('workshop_generator.errors.workshop_id_or_provider_required'));
      setIsLoading(false);
      return;
    }

    try {
      const response = await api.post('/api/tools/generate_workshop_description', {
        item_id: finalItemId,
        project_id: finalProjectId,
        user_template: userTemplate,
        target_language: targetLanguage,
        custom_language: customLanguage,
        api_provider: selectedProvider
      });
      setGeneratedBbcode(response.data.bbcode);
      const message = response.data.saved_path
        ? `${t('workshop_generator.messages.generation_successful')} ${response.data.saved_path}`
        : response.data.message || t('workshop_generator.messages.generation_successful_no_save');
      setSuccessMessage(message);
      notifications.show({ title: 'Success', message, color: 'green' });

    } catch (err) {
      const errorMessage = err.response?.data?.detail || t('workshop_generator.errors.generation_failed');
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Render ---
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px', position: 'relative' }}>
      <LoadingOverlay visible={isLoading} />
      <Title order={3}>{t('workshop_generator.title')}</Title>
      <Text>{t('workshop_generator.description')}</Text>

      <Group direction="column" grow mt="lg">

        {/* Input Mode */}
        <Radio.Group value={inputMode} onChange={setInputMode}>
          <Group>
            <Radio value="project" label={t('workshop_generator.input_mode.project')} />
            <Radio value="manual" label={t('workshop_generator.input_mode.manual')} />
          </Group>
        </Radio.Group>

        {/* Input Area */}
        {inputMode === 'project' ? (
          <Select
            value={selectedProjectId}
            onChange={setSelectedProjectId}
            data={projects.map(p => ({ label: p.name, value: p.project_id }))}
            placeholder={t('workshop_generator.placeholders.select_project')}
          />
        ) : (
          <Autocomplete
            value={manualItemId}
            onChange={handleManualIdChange}
            placeholder={t('workshop_generator.placeholders.manual_input')}
            data={[]}
          />
        )}

        {/* User Template */}
        <Textarea
          label={<Title order={5}>{t('workshop_generator.template_title')}</Title>}
          minRows={10}
          value={userTemplate}
          onChange={(e) => setUserTemplate(e.currentTarget.value)}
          placeholder={t('workshop_generator.placeholders.template_input')}
        />

        {/* Configuration */}
        <Group grow>
          <Select
            label={t('workshop_generator.labels.target_language')}
            value={targetLanguage}
            onChange={setTargetLanguage}
            data={[
              ...languages.map(lang => ({ value: lang.code, label: lang.name })),
              { value: 'custom', label: t('workshop_generator.languages.custom') }
            ]}
          />

          {targetLanguage === 'custom' && (
            <TextInput
              value={customLanguage}
              onChange={(e) => setCustomLanguage(e.currentTarget.value)}
              placeholder={t('workshop_generator.placeholders.custom_language')}
            />
          )}

          <Select
            label={t('workshop_generator.labels.api_provider')}
            value={selectedProvider}
            onChange={setSelectedProvider}
            placeholder={t('workshop_generator.placeholders.select_provider')}
            data={apiProviders}
          />
        </Group>

        {/* Controls */}
        <Button onClick={handleGenerate} loading={isLoading} fullWidth>
          {t('workshop_generator.buttons.generate')}
        </Button>

        {/* Messages */}
        {error && <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">{error}</Alert>}
        {successMessage && <Alert icon={<IconAlertCircle size={16} />} title="Success" color="green">{successMessage}</Alert>}

        {/* Output Area */}
        {generatedBbcode && (
          <div>
            <Group justify="space-between">
              <Title order={5}>{t('workshop_generator.output_title')}</Title>
              <CopyButton value={generatedBbcode}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied' : t('workshop_generator.buttons.copy')}>
                    <ActionIcon color={copied ? 'teal' : 'gray'} onClick={copy}>
                      <IconCopy size={16} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            <Textarea
              minRows={15}
              value={generatedBbcode}
              readOnly
              styles={{ input: { fontFamily: 'monospace', backgroundColor: 'var(--mantine-color-gray-1)' } }}
            />
          </div>
        )}

      </Group>
    </div>
  );
};

export default WorkshopGenerator;
