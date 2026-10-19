import { TagsInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';

// Suggestions, not a claim that each game has an official tag category.
const commonTags = ['Translation', 'Localization', 'Chinese', 'English', 'French',
  'German', 'Gameplay', 'Graphics', 'Utilities'];

export default function PublicationTagsInput({ value, onChange, disabled }) {
  const { t } = useTranslation();
  return <TagsInput
    label={t('workshop_publication.tags')}
    description={t('workshop_publication.tags_hint',
      'Choose a suggested tag or type your own and press Enter. Commas also separate tags.')}
    data={commonTags} value={value} onChange={onChange} disabled={disabled}
    splitChars={[',', '，']} clearable
  />;
}
