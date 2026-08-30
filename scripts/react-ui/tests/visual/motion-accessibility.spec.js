import { expect, test } from '@playwright/test';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];

for (const themeId of themes) {
  test(`${themeId} exposes keyboard-continuous desktop workspaces`, async ({ page }) => {
    await page.setViewportSize({ width: 2560, height: 1440 });
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=judgment-court`);
    await expect(page.getByTestId('judgment-court-visual-fixture')).toHaveAttribute(
      'data-visual-ready',
      'true',
    );

    const candidates = page.locator('[aria-controls="neologism-review-panel"]');
    await candidates.first().focus();
    await candidates.first().press('End');
    await expect(candidates.last()).toBeFocused();
    await expect(candidates.last()).toHaveAttribute('aria-pressed', 'true');

    const caseMotion = await page.getByTestId('neologism-review-workspace').evaluate(
      (element) => getComputedStyle(element).animationName,
    );
    expect(caseMotion).toContain('judgment-case-enter');

    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=project-management-kanban-normal`);
    await expect(page.getByTestId('project-management-kanban-normal')).toHaveAttribute(
      'data-visual-ready',
      'true',
    );

    const addNoteButtons = page.locator('#kanban-board button[aria-label]');
    await expect(addNoteButtons).toHaveCount(5);
    const accessibleNames = await addNoteButtons.evaluateAll((buttons) => (
      buttons.map((button) => button.getAttribute('aria-label'))
    ));
    expect(new Set(accessibleNames).size).toBe(5);

    const firstAddNote = addNoteButtons.first();
    const targetBox = await firstAddNote.boundingBox();
    expect(targetBox.width).toBeGreaterThanOrEqual(44);
    expect(targetBox.height).toBeGreaterThanOrEqual(44);
    await firstAddNote.focus();
    await expect(firstAddNote).toBeFocused();
    const focusStyle = await firstAddNote.evaluate((element) => {
      const style = getComputedStyle(element);
      return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
    });
    expect(focusStyle.outlineStyle).toBe('solid');
    expect(Number.parseFloat(focusStyle.outlineWidth)).toBeGreaterThanOrEqual(2);

    const taskLabels = await page.locator('[data-task-kind]').evaluateAll((cards) => (
      cards.map((card) => card.getAttribute('aria-label'))
    ));
    expect(taskLabels.length).toBeGreaterThan(0);
    expect(taskLabels.every(Boolean)).toBeTruthy();
  });

  test(`${themeId} honors reduced motion`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.setViewportSize({ width: 2560, height: 1440 });
    await page.goto(`/visual-fixtures.html?theme=${themeId}&contract=judgment-court`);
    await expect(page.getByTestId('judgment-court-visual-fixture')).toHaveAttribute(
      'data-visual-ready',
      'true',
    );

    const motion = await page.getByTestId('neologism-review-workspace').evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        animationName: style.animationName,
        animationDuration: style.animationDuration,
        transitionDuration: style.transitionDuration,
      };
    });
    expect(motion.animationName).toBe('none');
    expect(['0s', '0.001s']).toContain(motion.animationDuration);
    expect(['0s', '0.001s']).toContain(motion.transitionDuration);
  });
}
