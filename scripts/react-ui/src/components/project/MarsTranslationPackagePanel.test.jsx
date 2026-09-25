import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import translationPackageService from '../../services/translationPackageService';
import MarsTranslationPackagePanel from './MarsTranslationPackagePanel';

vi.mock('../../services/translationPackageService', () => ({
  default: {
    getOptions: vi.fn(),
    createPlan: vi.fn(),
    createPackage: vi.fn(),
  },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options) => options ? `${key}:${JSON.stringify(options)}` : key,
    i18n: { language: 'en' },
  }),
}));

const optionsResponse = {
  data: {
    supported: true,
    source_mod: { id: 'original-mod', title: 'Original Mod' },
    translation_outputs: [{ output_folder_name: 'zhCN', path: 'C:/Remis/outputs/zhCN' }],
    languages: [{ code: 'zh-CN', name: '简体中文', game_language: 'Chinese' }],
    limitations: ['CSV translations only'],
  },
};

const planResponse = {
  data: {
    plan_id: 'plan-1',
    summary: 'Will package translated CSV only',
    requires_approval: true,
    package: {
      mod_id: 'original-mod-zh-CN',
      title: 'Original Mod — 简体中文',
      language: 'Chinese',
      files: [{ path: 'translations/Chinese.csv', size_bytes: 128 }],
      total_size_bytes: 128,
    },
    warnings: ['No in-game verification'],
    installation_steps: ['Enable the translation package after the source mod.'],
  },
};

const renderPanel = (gameId = 'surviving_mars') => render(
  <MantineProvider>
    <MarsTranslationPackagePanel projectId="mars-42" gameId={gameId} />
  </MantineProvider>,
);

describe('MarsTranslationPackagePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translationPackageService.getOptions.mockResolvedValue(optionsResponse);
    translationPackageService.createPlan.mockResolvedValue(planResponse);
    translationPackageService.createPackage.mockResolvedValue({
      data: {
        package_path: 'C:/Remis/outputs/packages/original-mod-zh-CN',
        files: ['About.xml', 'translations/Chinese.csv'],
        size_bytes: 512,
        installation_steps: ['Enable the generated package.'],
        runtime_verified: false,
      },
    });
  });

  it('previews output and requires a separate approval click before writing the package', async () => {
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.open' }));
    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.preview' }));

    expect(await screen.findByText('Will package translated CSV only')).toBeInTheDocument();
    expect(screen.getByText('translations/Chinese.csv')).toBeInTheDocument();
    expect(screen.getByText('No in-game verification')).toBeInTheDocument();
    expect(translationPackageService.createPlan).toHaveBeenCalledWith('mars-42', {
      output_folder_name: 'zhCN',
      target_language: 'zh-CN',
    });
    expect(translationPackageService.createPackage).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'mars_translation_package.generate' }));
    await waitFor(() => expect(translationPackageService.createPackage).toHaveBeenCalledWith('mars-42', {
      plan_id: 'plan-1',
      approved: true,
    }));
    expect(await screen.findAllByText('C:/Remis/outputs/packages/original-mod-zh-CN')).toHaveLength(2);
  });

  it('collects missing source metadata before requesting a plan', async () => {
    translationPackageService.getOptions.mockResolvedValue({
      data: { ...optionsResponse.data, source_mod: { id: '', title: '' } },
    });
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.open' }));
    fireEvent.change(await screen.findByLabelText('mars_translation_package.source_mod_id_label'), {
      target: { value: 'entered-mod-id' },
    });
    fireEvent.change(screen.getByLabelText('mars_translation_package.source_mod_title_label'), {
      target: { value: 'Entered title' },
    });
    fireEvent.change(screen.getByLabelText('mars_translation_package.author_label'), {
      target: { value: 'Translator' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'mars_translation_package.preview' }));

    await waitFor(() => expect(translationPackageService.createPlan).toHaveBeenCalledWith('mars-42', expect.objectContaining({
      output_folder_name: 'zhCN',
      target_language: 'zh-CN',
      source_mod_id: 'entered-mod-id',
      source_mod_title: 'Entered title',
      author: 'Translator',
    })));
  });

  it('discards a stale plan and asks for a fresh preview after the server rejects it', async () => {
    translationPackageService.createPackage.mockRejectedValue({
      response: { data: { detail: { code: 'stale_plan', message: 'Plan is stale' } } },
    });
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.open' }));
    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.preview' }));
    fireEvent.click(await screen.findByRole('button', { name: 'mars_translation_package.generate' }));

    expect(await screen.findByText('Plan is stale')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'mars_translation_package.generate' })).not.toBeInTheDocument();
  });

  it('is not rendered for other game projects', () => {
    renderPanel('rimworld');

    expect(screen.queryByRole('heading', { name: 'mars_translation_package.title' })).not.toBeInTheDocument();
    expect(translationPackageService.getOptions).not.toHaveBeenCalled();
  });
});
