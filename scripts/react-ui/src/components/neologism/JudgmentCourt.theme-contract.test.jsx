import React from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';
import styles from './JudgmentCourt.module.css';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const definitionsCss = readFileSync(
  resolve(process.cwd(), 'src/themes/definitions.css'),
  'utf8',
);
const reviewPageSource = readFileSync(
  resolve(process.cwd(), 'src/pages/NeologismReviewPage.jsx'),
  'utf8',
);
const themeIds = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];

function parseThemeTokens(themeId) {
  const block = definitionsCss.match(
    new RegExp(`\\[data-theme=['"]${themeId}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
  );

  return Object.fromEntries(
    [...block[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)]
      .map(([, name, value]) => [name, value]),
  );
}

function relativeLuminance(hex) {
  return hex
    .slice(1)
    .match(/../g)
    .map((value) => parseInt(value, 16) / 255)
    .map((value) => (
      value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4
    ))
    .reduce(
      (sum, value, index) => sum + (value * [0.2126, 0.7152, 0.0722][index]),
      0,
    );
}

function contrastRatio(foreground, background) {
  const values = [
    relativeLuminance(foreground),
    relativeLuminance(background),
  ].sort((a, b) => b - a);

  return (values[0] + 0.05) / (values[1] + 0.05);
}

describe.each(themeIds)('%s JudgmentCourt contrast contract', (themeId) => {
  const tokens = parseThemeTokens(themeId);

  it.each([
    ['surface-text-main', 'surface-bg-solid'],
    ['surface-text-muted', 'surface-bg-solid'],
    ['paper-text-main', 'paper-bg'],
    ['paper-text-muted', 'paper-bg'],
    ['interactive-accent-text', 'interactive-accent'],
  ])('%s remains readable on %s', (foreground, background) => {
    expect(
      contrastRatio(tokens[foreground], tokens[background]),
      `${themeId}: ${foreground} on ${background}`,
    ).toBeGreaterThanOrEqual(4.5);
  });
});

describe('JudgmentCourt semantic surfaces', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] },
        });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({
          data: {
            candidates: [{
              id: 1,
              original: 'Hyperlane Relay',
              suggestion: '跃迁中继',
              reasoning: 'Recurring game term',
              context_evidence: [{
                snippet: 'Hyperlane Relay activates.',
                source_file: 'events/relay_events.yml',
              }],
              duplicate_matches: [{
                entry_id: 'existing-1',
                source_term: 'Hyperlane Relay',
                glossary_name: 'Project Glossary',
              }],
            }],
          },
        });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
  });

  it('assigns canvas, surface, paper, and action contracts to the rendered workspace', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });

    expect(reviewPageSource).toContain('data-remis-surface="canvas"');
    expect(definitionsCss).toContain("[data-remis-action='primary']");
    expect(definitionsCss).toContain("[data-remis-action='danger-secondary']");
    expect(screen.getByTestId('judgment-court')).toHaveAttribute('data-remis-surface', 'canvas');
    expect(screen.getByTestId('neologism-project-toolbar')).toHaveAttribute(
      'data-remis-surface',
      'surface',
    );
    expect(screen.getByTestId('neologism-candidate-anchor')).toHaveAttribute(
      'data-remis-surface',
      'surface',
    );
    expect(screen.getByTestId('neologism-analysis-panel')).toHaveAttribute(
      'data-remis-surface',
      'paper',
    );
    expect(screen.getByTestId('neologism-evidence-card')).toHaveAttribute(
      'data-remis-surface',
      'paper',
    );
    expect(screen.getByTestId('neologism-decision-panel')).toHaveAttribute(
      'data-remis-surface',
      'surface',
    );
    expect(screen.getByTestId('neologism-approve-action')).toHaveAttribute(
      'data-remis-action',
      'primary',
    );
    expect(screen.getByTestId('neologism-reject-action')).toHaveAttribute(
      'data-remis-action',
      'danger-secondary',
    );
  });

  it('keeps medieval decision labels on the surface text contract', async () => {
    const medieval = parseThemeTokens('medieval');

    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });

    expect(screen.getByText('neologism_review.court.duplicate_resolution')).toHaveClass(
      styles.semanticFieldLabel,
    );
    expect(screen.getByText('neologism_review.court.final_translation')).toHaveClass(
      styles.semanticFieldLabel,
    );
    expect(screen.getByText('neologism_review.court.final_translation_desc')).toHaveClass(
      styles.semanticFieldDescription,
    );
    expect(
      contrastRatio(medieval['surface-text-main'], medieval['surface-bg-solid']),
    ).toBeGreaterThanOrEqual(4.5);
    expect(
      contrastRatio(medieval['surface-text-muted'], medieval['surface-bg-solid']),
    ).toBeGreaterThanOrEqual(4.5);
  });
});
