import React, { useState } from 'react';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import WorkshopGenerator from './WorkshopGenerator';
import { useDescriptionModelConfig } from '../steamWorkshop/description/useDescriptionModelConfig';
import { useDescriptionWorkspace } from '../steamWorkshop/description/useDescriptionWorkspace';

vi.mock('../steamWorkshop/description/useDescriptionWorkspace', () => ({
  useDescriptionWorkspace: vi.fn(),
}));

vi.mock('../steamWorkshop/description/useDescriptionModelConfig', () => ({
  useDescriptionModelConfig: vi.fn(),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

const baseWorkspace = {
  workspace_id: 'workspace-1',
  name: '测试工作区',
  project_id: 'project-1',
  workshop_item_id: '3538617386',
  current_description_version_id: null,
};

const emptyEditor = {
  bbcode: '',
  language: 'zh',
  parentVersionId: null,
};

let scenario;
let activeSetEditor;
const setEditorSpy = vi.fn();

const createVersion = (versionId, bbcode, sequence, language = 'zh-CN') => ({
  version_id: versionId,
  bbcode,
  language,
  sequence,
  source: 'manual',
});

const createScenario = (overrides = {}) => ({
  createWorkspace: vi.fn(),
  editor: { ...emptyEditor },
  error: '',
  generateCandidate: vi.fn(),
  isGenerating: false,
  isLoading: false,
  isSaving: false,
  saveCandidate: vi.fn(),
  selectWorkspace: vi.fn(),
  versions: [],
  workspace: { ...baseWorkspace },
  workspaces: [{ workspace_id: baseWorkspace.workspace_id, name: baseWorkspace.name }],
  ...overrides,
});

const expectedEditor = (version) => ({
  bbcode: version?.bbcode || '',
  language: version?.language || 'zh',
  parentVersionId: version?.version_id || null,
});

function renderGenerator() {
  return render(
    <MantineProvider>
      <WorkshopGenerator projectId="project-1" />
    </MantineProvider>,
  );
}

function openGenerationDialog() {
  fireEvent.click(screen.getByRole('button', { name: '模型生成' }));
  return screen.findByRole('dialog');
}

describe('WorkshopGenerator publishing regressions', () => {
  beforeEach(() => {
    setEditorSpy.mockReset();
    activeSetEditor = null;
    scenario = createScenario();

    useDescriptionWorkspace.mockImplementation(() => {
      const [editor, setEditorState] = useState(scenario.editor);
      const setEditor = (nextEditor) => {
        setEditorSpy(nextEditor);
        setEditorState(nextEditor);
      };
      activeSetEditor = setEditor;
      return { ...scenario, editor, setEditor };
    });

    useDescriptionModelConfig.mockReturnValue({
      isLoading: false,
      languageOptions: [{ value: 'zh-CN', label: '简体中文' }],
      loadConfig: vi.fn(),
      loadError: '',
      model: 'google/gemma-4-31b-qat',
      modelOptions: [{ value: 'google/gemma-4-31b-qat', label: 'google/gemma-4-31b-qat' }],
      missingApiKey: false,
      provider: 'lm_studio',
      providerOptions: [{ value: 'lm_studio', label: 'LM Studio' }],
      setModel: vi.fn(),
      setProvider: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('initializes the editor with adopted, then latest, then empty content', async () => {
    const latest = createVersion('version-latest', '[b]最新候选[/b]', 3);
    const adopted = createVersion('version-adopted', '[b]当前采用[/b]', 2, 'en');
    scenario = createScenario({
      versions: [latest, adopted],
      workspace: {
        ...baseWorkspace,
        current_description_version_id: adopted.version_id,
      },
    });

    renderGenerator();

    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: 'Steam BBCode' })).toHaveValue(adopted.bbcode);
    });
    expect(setEditorSpy).toHaveBeenCalledWith(expectedEditor(adopted));
    expect(screen.queryByLabelText('父版本')).not.toBeInTheDocument();
    expect(screen.getByLabelText('手工候选语言')).toHaveValue(adopted.language);

    cleanup();
    setEditorSpy.mockReset();
    scenario = createScenario({
      versions: [latest, adopted],
      workspace: { ...baseWorkspace },
    });
    renderGenerator();

    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: 'Steam BBCode' })).toHaveValue(latest.bbcode);
    });
    expect(setEditorSpy).toHaveBeenCalledWith(expectedEditor(latest));

    cleanup();
    setEditorSpy.mockReset();
    scenario = createScenario();
    renderGenerator();

    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: 'Steam BBCode' })).toHaveValue('');
    });
    expect(setEditorSpy).toHaveBeenCalledWith(expectedEditor(null));
  });

  it('closes the generation dialog only after a persisted candidate is returned', async () => {
    const latest = createVersion('version-latest', '[b]最新候选[/b]', 3);
    const adopted = createVersion('version-adopted', '[b]当前采用[/b]', 2, 'en');
    const generated = createVersion('version-generated', '[b]新生成候选[/b]', 4);
    scenario = createScenario({
      versions: [latest, adopted],
      workspace: {
        ...baseWorkspace,
        current_description_version_id: adopted.version_id,
      },
    });
    scenario.generateCandidate.mockImplementation(async () => {
      activeSetEditor(expectedEditor(generated));
      return generated;
    });

    renderGenerator();
    await waitFor(() => {
      expect(screen.getByRole('textbox', { name: 'Steam BBCode' })).toHaveValue(adopted.bbcode);
    });

    const dialog = await openGenerationDialog();
    fireEvent.click(within(await dialog).getByRole('checkbox', {
      name: '我确认执行这次模型调用，并将结果保存为候选版本',
    }));
    fireEvent.click(within(await dialog).getByRole('button', { name: '确认生成' }));

    await waitFor(() => expect(scenario.generateCandidate).toHaveBeenCalledWith(
      expect.objectContaining({ approved: true }),
    ));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('textbox', { name: 'Steam BBCode' })).toHaveValue(adopted.bbcode);
    expect(setEditorSpy).toHaveBeenLastCalledWith(expectedEditor(adopted));
  });

  it('keeps the generation dialog open when persistence fails', async () => {
    scenario.generateCandidate.mockResolvedValue(null);
    renderGenerator();

    const dialog = await openGenerationDialog();
    fireEvent.click(within(await dialog).getByRole('checkbox', {
      name: '我确认执行这次模型调用，并将结果保存为候选版本',
    }));
    fireEvent.click(within(await dialog).getByRole('button', { name: '确认生成' }));

    await waitFor(() => expect(scenario.generateCandidate).toHaveBeenCalled());
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
