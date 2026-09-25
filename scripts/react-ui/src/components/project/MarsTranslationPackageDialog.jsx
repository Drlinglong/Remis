import React from 'react';
import { Alert, Modal, Stack, Text } from '@mantine/core';

import TranslationPackageCreatedSummary from './TranslationPackageCreatedSummary';
import TranslationPackageForm from './TranslationPackageForm';
import TranslationPackagePreview from './TranslationPackagePreview';

const errorMessageKey = (code) => ({
  stale_plan: 'stale_plan',
  approval_required: 'approval_required',
}[code] || 'unexpected_error');

export default function MarsTranslationPackageDialog({ opened, onClose, packageFlow, t, locale }) {
  const options = packageFlow.options;
  const showForm = options?.supported !== false && !packageFlow.loading && options;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('mars_translation_package.title')}
      centered
      size="lg"
      data-remis-surface="elevated"
    >
      <Stack gap="md">
        {packageFlow.loading && <Text role="status">{t('mars_translation_package.loading')}</Text>}
        {packageFlow.error && (
          <Alert color="red" title={t('mars_translation_package.error_title')}>
            {packageFlow.errorMessage || t(`mars_translation_package.errors.${errorMessageKey(packageFlow.error)}`)}
          </Alert>
        )}
        {options?.supported === false && <Alert color="yellow">{t('mars_translation_package.unsupported')}</Alert>}
        {options?.limitations?.length > 0 && (
          <Alert color="yellow" title={t('mars_translation_package.limitations_title')}>
            <ul>{options.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
          </Alert>
        )}
        {options?.warnings?.length > 0 && (
          <Alert color="yellow" title={t('mars_translation_package.limitations_title')}>
            <ul>{options.warnings.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
          </Alert>
        )}
        {showForm && <TranslationPackageForm packageFlow={packageFlow} t={t} />}
        {packageFlow.plan && (
          <TranslationPackagePreview plan={packageFlow.plan} packageFlow={packageFlow} t={t} locale={locale} />
        )}
        {packageFlow.result && (
          <TranslationPackageCreatedSummary result={packageFlow.result} t={t} locale={locale} />
        )}
      </Stack>
    </Modal>
  );
}
