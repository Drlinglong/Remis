import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { FEATURES } from './features';
import {
  ENTRY_MODES,
  NAVIGATION_SECTIONS,
  PAGE_DOMAINS,
  PAGE_REGISTRY,
  buildAppRouteConfig,
  getNavigationSections,
  resolveRegisteredPage,
} from './pageRegistry';

describe('pageRegistry', () => {
  it('registers Steam Workshop as a primary publishing page', () => {
    const page = PAGE_REGISTRY.find((item) => item.id === 'steam-workshop');

    expect(page.routePaths).toContain('/steam-workshop');
    expect(page.routePaths).toContain('/steam-workshop/:workspaceId/:section');
    expect(page.domain).toBe(PAGE_DOMAINS.PUBLISHING);
    expect(page.navigation.entryMode).toBe(ENTRY_MODES.PRIMARY);
  });

  it('keeps route ids and route paths unique', () => {
    const ids = PAGE_REGISTRY.map((page) => page.id);
    const paths = PAGE_REGISTRY.flatMap((page) => page.routePaths);

    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('assigns every primary page to one stable domain without a catch-all section', () => {
    const allowedDomains = new Set(Object.values(PAGE_DOMAINS));
    const sectionPageIds = NAVIGATION_SECTIONS.flatMap((section) => section.pageIds);
    const enabledPrimaryPages = PAGE_REGISTRY.filter((page) => (
      (!page.enabledBy || FEATURES[page.enabledBy])
      && page.navigation?.entryMode === ENTRY_MODES.PRIMARY
      && page.navigation.section !== 'settings'
      && page.navigation.section !== 'documentation'
    ));

    enabledPrimaryPages.forEach((page) => {
      expect(allowedDomains.has(page.domain)).toBe(true);
      expect(page.navigation.section).not.toMatch(/^(more|misc|other)$/);
      expect(sectionPageIds.filter((pageId) => pageId === page.id)).toHaveLength(1);
    });
  });

  it('exposes Copilot as a dedicated primary entry only when its feature is enabled', () => {
    const copilot = PAGE_REGISTRY.find((page) => page.id === 'copilot');
    const stableSections = getNavigationSections({
      ...FEATURES,
      ENABLE_REMIS_COPILOT: false,
    });
    const previewSections = getNavigationSections({
      ...FEATURES,
      ENABLE_REMIS_COPILOT: true,
    });

    expect(copilot.domain).toBe(PAGE_DOMAINS.ASSISTANT);
    expect(copilot.navigation.entryMode).toBe(ENTRY_MODES.PRIMARY);
    expect(copilot.navigation.section).toBe('assistant');
    expect(NAVIGATION_SECTIONS.flatMap((section) => section.pageIds)).toContain('copilot');
    expect(stableSections.find((section) => section.id === 'assistant')?.pages).toHaveLength(0);
    expect(previewSections.find((section) => section.id === 'assistant')?.pages.map((page) => page.id)).toEqual(['copilot']);
  });

  it('builds routes from the same page identities used by navigation', () => {
    const pageElements = Object.fromEntries(PAGE_REGISTRY.map((page) => [page.id, page.id]));
    const routes = buildAppRouteConfig(pageElements, FEATURES);

    getNavigationSections(FEATURES)
      .flatMap((section) => section.pages)
      .forEach((page) => {
        expect(routes.some((route) => route.path === page.routePaths[0] && route.element === page.id)).toBe(true);
      });
  });

  it('resolves route-aware Copilot context from the registry', () => {
    const projectManagement = resolveRegisteredPage('/project-management/demo');

    expect(projectManagement?.id).toBe('project-management');
    expect(projectManagement?.guide).toBe('docs/zh/user-guides/project-management.md');
    expect(projectManagement?.copilot.helpSkillId).toBe('project_management');
    expect(resolveRegisteredPage('/tasks/task-1/glossary-health')?.id).toBe('glossary-health-review');
    expect(resolveRegisteredPage('/model-arena')?.copilot.pageName).toContain('Model Arena');
    expect(resolveRegisteredPage('/steam-workshop/workspace-1/history')?.id).toBe('steam-workshop');
  });

  it('keeps declared navigation guides on disk', () => {
    const repositoryRoot = path.resolve(process.cwd(), '..', '..');

    PAGE_REGISTRY
      .filter((page) => page.navigation?.entryMode === ENTRY_MODES.PRIMARY && page.guide)
      .forEach((page) => {
        expect(fs.existsSync(path.join(repositoryRoot, page.guide)), `${page.id} guide is missing`).toBe(true);
      });
  });
});
