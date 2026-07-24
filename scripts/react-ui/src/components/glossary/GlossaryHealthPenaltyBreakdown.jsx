import React, { useMemo } from 'react';
import { Badge, Group } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { getGlossaryHealthPenaltyBreakdown } from '../../utils/glossaryHealthScore';

const GlossaryHealthPenaltyBreakdown = ({ issues }) => {
  const { t } = useTranslation();
  const breakdown = useMemo(
    () => getGlossaryHealthPenaltyBreakdown(issues),
    [issues],
  );

  if (!breakdown.totalPenalty) {
    return (
      <Badge color="teal" variant="outline" data-testid="glossary-health-penalty-breakdown">
        {t('glossary_health_penalty_none')}
      </Badge>
    );
  }

  return (
    <Group gap={6} wrap="wrap" data-testid="glossary-health-penalty-breakdown">
      {breakdown.error.findings > 0 && (
        <Badge color="red" variant="outline">
          {t('glossary_health_penalty_error', {
            count: breakdown.error.findings,
            points: breakdown.error.penalty,
          })}
        </Badge>
      )}
      {breakdown.warning.findings > 0 && (
        <Badge color="orange" variant="outline">
          {t('glossary_health_penalty_warning', {
            count: breakdown.warning.findings,
            points: breakdown.warning.penalty,
          })}
        </Badge>
      )}
      {breakdown.info.findings > 0 && (
        <Badge color="blue" variant="outline">
          {t('glossary_health_penalty_info', {
            count: breakdown.info.findings,
            points: breakdown.info.penalty,
          })}
        </Badge>
      )}
    </Group>
  );
};

export default GlossaryHealthPenaltyBreakdown;
