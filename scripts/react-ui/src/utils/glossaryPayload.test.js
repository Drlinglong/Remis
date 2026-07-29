import { describe, expect, it } from 'vitest';

import {
  normalizeGlossaryContentPayload,
  normalizeGlossaryOverviewPayload,
  normalizeGlossaryProjectsPayload,
  normalizeGlossaryTaskHistoryPayload,
  normalizeGlossaryTreePayload,
} from './glossaryPayload';

describe('glossary payload normalization', () => {
  it('accepts bare arrays and common wrapper payloads', () => {
    expect(normalizeGlossaryTreePayload({ tree: [{ key: 'vic3' }] })).toEqual([{ key: 'vic3' }]);
    expect(normalizeGlossaryProjectsPayload({ data: { projects: [{ project_id: 'demo' }] } })).toEqual([
      { project_id: 'demo' },
    ]);
    expect(normalizeGlossaryTaskHistoryPayload({ data: { tasks: [{ task_id: 'health-1' }] } })).toEqual([
      { task_id: 'health-1' },
    ]);
  });

  it('normalizes glossary overview and content records', () => {
    expect(normalizeGlossaryOverviewPayload({
      data: {
        overview: {
          summary: { glossary_count: 1 },
          glossaries: [{ glossary_id: 7 }],
        },
      },
    })).toEqual(expect.objectContaining({
      summary: expect.objectContaining({ glossary_count: 1, term_count: 0 }),
      glossaries: [{ glossary_id: 7 }],
    }));

    expect(normalizeGlossaryContentPayload({
      data: {
        content: {
          entries: [{ id: 'entry-1' }],
          total_count: 4,
        },
      },
    })).toEqual({
      entries: [{ id: 'entry-1' }],
      totalCount: 4,
    });
  });

  it('falls back to safe empty collections for malformed payloads', () => {
    expect(normalizeGlossaryTreePayload({ tree: 'invalid' })).toEqual([]);
    expect(normalizeGlossaryProjectsPayload(null)).toEqual([]);
    expect(normalizeGlossaryTaskHistoryPayload({ tasks: {} })).toEqual([]);
    expect(normalizeGlossaryContentPayload({ entries: 'invalid' })).toEqual({
      entries: [],
      totalCount: 0,
    });
    expect(normalizeGlossaryOverviewPayload({ glossaries: 'invalid' })).toEqual(expect.objectContaining({
      glossaries: [],
      summary: expect.objectContaining({ glossary_count: 0 }),
    }));
  });
});
