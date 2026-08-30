import { describe, expect, it } from 'vitest';

import {
  getLocalizationWorkflowMissingInputs,
  resolveCopilotProject,
} from './localizationWorkflowReadiness';

describe('localization workflow readiness', () => {
  it('accepts the canonical backend target_languages contract', () => {
    expect(getLocalizationWorkflowMissingInputs({
      project_mode: 'existing',
      project_id: 'project-1',
      target_languages: ['zh-CN', 'ja'],
      api_provider: 'openrouter',
      model: 'openai/gpt-5.6-luna',
    })).toEqual([]);
  });

  it('requires an existing-project reference and all new-project source fields', () => {
    expect(getLocalizationWorkflowMissingInputs({
      project_mode: 'existing',
      target_languages: ['zh-CN'],
    })).toContain('已有项目');
    expect(getLocalizationWorkflowMissingInputs({
      project_mode: 'new',
      project_name: 'A proposed name is not an existing-project reference',
      target_languages: ['zh-CN'],
    })).toEqual(['Mod 路径', '游戏', '源语言']);
  });

  it('does not guess when a shortened project name matches multiple projects', () => {
    const result = resolveCopilotProject([
      { project_id: 'one', name: 'Project Remis - Demo Mod - Stellaris', game_id: 'stellaris' },
      { project_id: 'two', name: 'Project Remis - Demo Mod - Archive', game_id: 'stellaris' },
    ], {
      project_mode: 'existing',
      project_name: 'Project Remis - Demo Mod',
      game_id: 'stellaris',
    });

    expect(result).toEqual({ project: null, matchCount: 2 });
  });
});
