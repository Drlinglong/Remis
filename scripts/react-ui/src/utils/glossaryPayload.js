import { normalizeArrayPayload } from './payload';

export const EMPTY_GLOSSARY_OVERVIEW = {
  summary: {
    game_count: 0,
    glossary_count: 0,
    term_count: 0,
    main_glossary_count: 0,
    project_glossary_count: 0,
    bound_project_count: 0,
  },
  glossaries: [],
};

const unwrapRecordPayload = (payload, keys) => {
  let current = payload;

  for (let depth = 0; depth < 3; depth += 1) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) return {};

    const nested = keys
      .map((key) => current[key])
      .find((candidate) => (
        candidate
        && typeof candidate === 'object'
        && !Array.isArray(candidate)
      ));
    if (!nested) return current;
    current = nested;
  }

  return current;
};

const normalizeNestedArrayPayload = (payload, keys) => {
  let current = payload;

  for (let depth = 0; depth < 3; depth += 1) {
    if (Array.isArray(current)) return current;
    if (!current || typeof current !== 'object') return [];

    for (const key of keys) {
      if (Array.isArray(current[key])) return current[key];
    }

    current = current.data ?? current.result ?? current.payload;
  }

  return [];
};

export const normalizeGlossaryTreePayload = (payload) => (
  normalizeNestedArrayPayload(payload, ['tree', 'items', 'data', 'results'])
);

export const normalizeGlossaryProjectsPayload = (payload) => (
  normalizeNestedArrayPayload(payload, ['projects', 'items', 'data', 'results'])
);

export const normalizeGlossaryOverviewPayload = (payload) => {
  const overview = unwrapRecordPayload(payload, ['overview', 'data', 'result']);
  return {
    summary: {
      ...EMPTY_GLOSSARY_OVERVIEW.summary,
      ...(overview.summary && typeof overview.summary === 'object' ? overview.summary : {}),
    },
    glossaries: normalizeArrayPayload(
      overview.glossaries ?? overview,
      ['glossaries', 'items', 'data', 'results']
    ),
  };
};

export const normalizeGlossaryContentPayload = (payload) => {
  const content = unwrapRecordPayload(payload, ['content', 'data', 'result']);
  const entries = normalizeArrayPayload(
    content.entries ?? content,
    ['entries', 'items', 'data', 'results']
  );
  const parsedTotal = Number(content.totalCount ?? content.total_count);

  return {
    entries,
    totalCount: Number.isFinite(parsedTotal) && parsedTotal >= 0
      ? parsedTotal
      : entries.length,
  };
};

export const normalizeGlossaryTaskHistoryPayload = (payload) => (
  normalizeNestedArrayPayload(payload, ['tasks', 'items', 'data', 'results'])
);
