import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import i18next from 'i18next';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import deLocale from '../../i18n/locales/de/translation.json';
import ruLocale from '../../i18n/locales/ru/translation.json';
import SteamWorkshopOverview from './SteamWorkshopOverview';

let workspaces = [];

vi.mock('./usePublishingWorkspaceCatalog', () => ({
  usePublishingWorkspaceCatalog: () => ({
    error: '',
    games: [],
    isLoading: false,
    isSaving: false,
    projectNames: new Map(),
    projects: [],
    saveWorkspace: vi.fn(),
    workspaces,
  }),
}));

const germanI18n = i18next.createInstance();
germanI18n.init({
  initImmediate: false,
  lng: 'de',
  resources: { de: { translation: deLocale } },
});

const russianI18n = i18next.createInstance();
russianI18n.init({
  initImmediate: false,
  lng: 'ru',
  resources: { ru: { translation: ruLocale } },
});

describe('SteamWorkshopOverview localization', () => {
  it('renders a non-Chinese release locale instead of source-language copy', () => {
    render(
      <I18nextProvider i18n={germanI18n}>
        <MantineProvider>
          <MemoryRouter>
            <SteamWorkshopOverview />
          </MemoryRouter>
        </MantineProvider>
      </I18nextProvider>,
    );

    expect(screen.getByRole('heading', { name: 'Steam-Workshop' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Arbeitsbereich erstellen' })).toBeInTheDocument();
    expect(screen.queryByText('新建工作区')).not.toBeInTheDocument();
  });

  it('formats workspace updates with the resolved Russian UI locale', () => {
    workspaces = [{
      workspace_id: 'workspace-ru',
      name: 'Russian workspace',
      updated_at: '2026-08-01T12:18:00Z',
      cover_version_count: 0,
      description_version_count: 0,
    }];

    render(
      <I18nextProvider i18n={russianI18n}>
        <MantineProvider>
          <MemoryRouter>
            <SteamWorkshopOverview />
          </MemoryRouter>
        </MantineProvider>
      </I18nextProvider>,
    );

    const update = screen.getByText(/^Последнее обновление:/);
    expect(update).toHaveTextContent(/авг\.?/i);
    expect(update).not.toHaveTextContent(/[年月日]/);
  });
});
