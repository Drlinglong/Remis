import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const read = (relativeFile) => readFileSync(new URL(relativeFile, import.meta.url), 'utf8');

describe('Home phase 2 architecture contract', () => {
  it('keeps page wiring thin and views free of transport/context imports', () => {
    const page = read('../HomePage.jsx');
    const dashboardView = read('./HomeDashboardView.jsx');
    const liveWorkView = read('./HomeLiveWorkSection.jsx');

    expect(page.split(/\r?\n/).length).toBeLessThanOrEqual(110);
    expect(page).not.toMatch(/from ['"].*utils\/api/);
    expect(page).not.toContain('useTaskCenter');
    expect(dashboardView).not.toMatch(/from ['"].*utils\/api/);
    expect(dashboardView).not.toContain('useTaskCenter');
    expect(liveWorkView).not.toMatch(/from ['"].*utils\/api/);
    expect(liveWorkView).not.toContain('useTaskCenter');
  });

  it('leaves page scrolling to MainLayout and removes the activity ScrollArea', () => {
    const css = read('../HomePage.module.css');
    const activity = read('../../components/RecentActivityList.jsx');
    const layout = read('../../components/layout/MainLayout.jsx');

    expect(css).not.toMatch(/100vh|overflow-(?:x|y)\s*:/);
    expect(activity).not.toContain('ScrollArea');
    expect(activity).not.toMatch(/h=\{300\}/);
    expect(layout.match(/data-remis-scroll-owner="main-content"/g)).toHaveLength(1);
  });
});
