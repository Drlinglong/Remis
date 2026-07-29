import { describe, expect, it } from 'vitest';
import { getTutorialSteps } from './tutorialSteps';

const t = (key) => key;

describe('tutorialSteps', () => {
  it('provides incremental translation tutorial steps for each workflow stage', () => {
    [
      'incremental-translation-step-0',
      'incremental-translation-step-1',
      'incremental-translation-step-2',
      'incremental-translation-step-3',
    ].forEach((pageName) => {
      expect(getTutorialSteps(t, pageName).length).toBeGreaterThan(0);
    });
  });

  it('provides project management tutorial steps for dashboard detail tabs', () => {
    [
      'project-management-validation',
      'project-management-history',
    ].forEach((pageName) => {
      expect(getTutorialSteps(t, pageName).length).toBeGreaterThan(0);
    });
  });

  it('provides agent workshop tutorial steps for each workflow stage', () => {
    [
      'agent-workshop-step-0',
      'agent-workshop-step-1',
      'agent-workshop-step-2',
      'agent-workshop-step-3',
    ].forEach((pageName) => {
      expect(getTutorialSteps(t, pageName).length).toBeGreaterThan(0);
    });
  });

  it('covers the task, glossary health, and neologism modules added to the current navigation', () => {
    [
      'neologism-mining',
      'neologism-court',
      'task-history',
      'task-detail',
      'glossary-health-review',
    ].forEach((pageName) => {
      expect(getTutorialSteps(t, pageName).length).toBeGreaterThan(0);
    });
  });

  it('targets the current homepage and project dashboard structure', () => {
    expect(getTutorialSteps(t, 'home').map((step) => step.element)).toEqual(expect.arrayContaining([
      '#homepage-workspace-header',
      '#homepage-live-work',
      '#homepage-project-portfolio',
      '#recent-activity',
    ]));
    expect(getTutorialSteps(t, 'project-management-dashboard').map((step) => step.element)).toEqual(expect.arrayContaining([
      '#project-dashboard-header',
      '#project-dashboard-tabs',
      '#project-dashboard-overview',
    ]));
  });
});
