import React, { useEffect, useState } from 'react';
import { Alert, Modal, Stack, Text, Textarea } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import api from '../../utils/api';

const ProjectSourcePreviewModal = ({ file, onClose, projectId }) => {
  const { t } = useTranslation();
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!file) return undefined;
    const controller = new AbortController();
    setPreview(null);
    setError(null);
    setLoading(true);

    api.get(`/api/projects/${encodeURIComponent(projectId)}/game-resources/${encodeURIComponent(file.key)}/preview`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (response.data?.read_only !== true) {
          throw new Error('Source preview response did not confirm read-only access.');
        }
        setPreview(response.data);
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) setError(requestError);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [file, projectId]);

  return (
    <Modal
      opened={Boolean(file)}
      onClose={onClose}
      title={t('project_management.source_view_title', { defaultValue: 'Source file (read only)' })}
      size="xl"
    >
      {file && (
        <Stack>
          <Text size="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>{preview?.file_path || file.name}</Text>
          {loading && <Text role="status">{t('project_management.source_view_loading', { defaultValue: 'Loading source file…' })}</Text>}
          {error && <Alert color="red">{t('project_management.source_view_error', { defaultValue: 'Could not read this source file.' })}</Alert>}
          {!loading && !error && (
            <Textarea
              aria-label={t('project_management.source_view_content', { defaultValue: 'Source file content' })}
              value={String(preview?.content || '')}
              readOnly
              autosize
              minRows={12}
              maxRows={28}
              styles={{ input: { fontFamily: 'monospace', whiteSpace: 'pre', overflowX: 'auto' } }}
            />
          )}
        </Stack>
      )}
    </Modal>
  );
};

export default ProjectSourcePreviewModal;
