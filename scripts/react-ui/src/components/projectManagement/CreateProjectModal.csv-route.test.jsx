import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { CreateProjectModal } from './CreateProjectModal';

vi.mock('../project/MarsPipelineImport', () => ({
  default: ({ opened, onUseExistingCsv }) => (
    opened ? <button type="button" onClick={onUseExistingCsv}>Use existing CSV folder</button> : null
  ),
}));

describe('CreateProjectModal existing-CSV route', () => {
  it('resets a Japanese source language to English before entering Mars CSV mode', async () => {
    const setSourceLanguage = vi.fn();
    const setNoop = vi.fn();
    render(
      <MantineProvider>
        <CreateProjectModal
          availableGames={[{
            value: 'surviving_mars',
            label: 'Surviving Mars',
            supported_language_codes: ['zh-CN', 'en', 'fr', 'de', 'es', 'pl', 'pt-BR', 'ru', 'tr'],
          }]}
          availableLanguages={[]}
          createProgressMessage=""
          handleBrowseFolder={vi.fn()}
          handleCreateProject={vi.fn()}
          isCreatingProject={false}
          newProjectGame="surviving_mars"
          newProjectImportMode="copy"
          newProjectName="Sample"
          newProjectPath="C:/mods/sample"
          newProjectSourceLang="ja"
          opened
          setNewProjectGame={setNoop}
          setNewProjectImportMode={setNoop}
          setNewProjectName={setNoop}
          setNewProjectPath={setNoop}
          setNewProjectSourceLang={setSourceLanguage}
          t={(key, fallback) => fallback || key}
          onClose={vi.fn()}
          onPipelineCreated={vi.fn()}
        />
      </MantineProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open FPK preparation' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Use existing CSV folder' }));

    expect(setSourceLanguage).toHaveBeenCalledWith('en');
  });
});
