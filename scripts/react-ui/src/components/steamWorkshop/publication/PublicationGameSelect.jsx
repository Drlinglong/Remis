import { useState } from 'react';
import { NumberInput, Select, Stack } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export default function PublicationGameSelect({ value, games, onChange, disabled }) {
  const { t } = useTranslation();
  const [manual, setManual] = useState(false);
  const options = games.map((game) => ({ value: String(game.app_id),
    label: `${game.app_id}（${t(`game_name_${game.game_id}`, game.name)}）` }));
  const known = options.some((option) => option.value === String(value));
  const custom = manual || (!!value && !known);
  return <Stack gap="xs" id="workshop-publication-game">
    <Select label={t('workshop_publication.app_id')} searchable disabled={disabled}
      data={[...options, { value: 'custom', label: t('workshop_publication.custom_app', 'Enter another App ID') }]}
      value={custom ? 'custom' : value ? String(value) : null}
      onChange={(selected) => {
        setManual(selected === 'custom');
        onChange(selected === 'custom' ? '' : selected || '');
      }} />
    {custom && <NumberInput label={t('workshop_publication.custom_app', 'Enter another App ID')}
      value={value} min={1} max={4294967295} allowDecimal={false} allowNegative={false}
      onChange={onChange} disabled={disabled} />}
  </Stack>;
}
