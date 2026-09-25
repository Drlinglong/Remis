import React from 'react';
import { Button, Tooltip } from '@mantine/core';
import { IconRocket, IconTrash } from '@tabler/icons-react';

import { allowsParadoxDeployment } from '../../utils/gameSupportPolicy';

export default function ParadoxCompletionActions({
  deployStatus,
  gameId,
  handleOpenCleanModal,
  handleOpenDeployModal,
  loadingIcon,
  t,
}) {
  if (!allowsParadoxDeployment(gameId)) return null;

  return (
    <>
      <Tooltip label={t('deploy_tooltip_label')} position="top" withArrow>
        <Button
          leftSection={deployStatus === 'loading' ? loadingIcon : <IconRocket size={20} />}
          size="lg"
          color={deployStatus === 'success' ? 'green' : (deployStatus === 'error' ? 'red' : 'blue')}
          onClick={handleOpenDeployModal}
          loading={deployStatus === 'loading'}
          disabled={deployStatus === 'success'}
        >
          {deployStatus === 'loading' ? t('button_deploying') : t('button_auto_deploy')}
        </Button>
      </Tooltip>
      <Tooltip label={t('deploy_clean_tooltip_label')} position="top" withArrow>
        <Button
          leftSection={<IconTrash size={20} />}
          size="lg"
          color="red"
          onClick={handleOpenCleanModal}
          disabled={deployStatus === 'loading'}
        >
          {t('button_clean_fake_loc')}
        </Button>
      </Tooltip>
    </>
  );
}
