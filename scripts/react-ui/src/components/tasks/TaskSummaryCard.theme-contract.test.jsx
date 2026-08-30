import { parse } from '@babel/parser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (file) => readFileSync(resolve(process.cwd(), file), 'utf8');

const taskSummarySource = readSource('src/components/tasks/TaskSummaryCard.jsx');

const PAPER_ACTION_VALUES = new Set([
  'paper-primary',
  'paper-secondary',
  'paper-danger',
]);

const PAPER_COMPONENT_SCAN_TABLE = [
  'src/components/modelArena/ArenaVoting.jsx',
  'src/components/neologism/PublishedArchiveContent.jsx',
  'src/components/neologism/archiveTreeV2/PublishedContextEventDetail.jsx',
  'src/components/steamWorkshop/PublishingVersionHistory.jsx',
  'src/components/steamWorkshop/WorkspaceCard.jsx',
  'src/components/tasks/TaskSummaryCard.jsx',
  'src/pages/AgentWorkshopPage.jsx',
  'src/pages/home/HomeDashboardView.jsx',
];

function getAttribute(element, name) {
  return element.openingElement?.attributes?.find(
    (attribute) => attribute.type === 'JSXAttribute' && attribute.name.name === name,
  );
}

function collectStringLiterals(node, values = []) {
  if (!node || typeof node !== 'object') return values;
  if (node.type === 'StringLiteral') values.push(node.value);
  Object.entries(node).forEach(([key, value]) => {
    if (['loc', 'start', 'end', 'extra'].includes(key)) return;
    if (Array.isArray(value)) {
      value.forEach((child) => collectStringLiterals(child, values));
    } else {
      collectStringLiterals(value, values);
    }
  });
  return values;
}

function actionValues(attribute) {
  if (!attribute?.value) return ['true'];
  if (attribute.value.type === 'StringLiteral') return [attribute.value.value];
  if (attribute.value.type === 'JSXExpressionContainer') {
    return collectStringLiterals(attribute.value.expression);
  }
  return [];
}

function scanPaperActions(node, paperDepth = 0, actions = []) {
  if (!node || typeof node !== 'object') return actions;
  if (node.type === 'JSXElement') {
    const surface = getAttribute(node, 'data-remis-surface');
    const action = getAttribute(node, 'data-remis-action');
    const isPaper = surface?.value?.type === 'StringLiteral'
      && surface.value.value === 'paper';
    const nextDepth = paperDepth + (isPaper ? 1 : 0);
    if (action && nextDepth > 0) {
      actions.push({ line: action.loc.start.line, values: actionValues(action) });
    }
    node.children.forEach((child) => scanPaperActions(child, nextDepth, actions));
    return actions;
  }
  if (Array.isArray(node)) {
    node.forEach((child) => scanPaperActions(child, paperDepth, actions));
    return actions;
  }
  Object.entries(node).forEach(([key, value]) => {
    if (['loc', 'start', 'end'].includes(key)) return;
    scanPaperActions(value, paperDepth, actions);
  });
  return actions;
}

function paperActionScan(file) {
  const source = readSource(file);
  const ast = parse(source, { sourceType: 'module', plugins: ['jsx'] });
  return scanPaperActions(ast);
}

describe('paper action semantic surface contract', () => {
  it('uses paper action variants on its paper surface', () => {
    expect(taskSummarySource).toContain('data-remis-surface="paper"');
    expect(taskSummarySource).toContain('data-remis-action="paper-secondary"');
    expect(taskSummarySource).not.toContain('data-remis-action="secondary"');
  });

  it('scans every registered paper component for non-paper action variants', () => {
    const violations = [];

    PAPER_COMPONENT_SCAN_TABLE.forEach((file) => {
      const source = readSource(file);
      expect(source).toContain('data-remis-surface="paper"');
      const actions = paperActionScan(file);
      expect(actions.length, `${file} must expose a scanned paper action`).toBeGreaterThan(0);
      actions.forEach(({ line, values }) => {
        if (values.length === 0) {
          violations.push(`${file}:${line} uses an opaque paper action expression`);
          return;
        }
        values.forEach((value) => {
          if (!PAPER_ACTION_VALUES.has(value)) {
            violations.push(`${file}:${line} uses ${value}`);
          }
        });
      });
    });

    expect(violations).toEqual([]);
  });
});
