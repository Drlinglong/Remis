export const normalizeArrayPayload = (payload, keys = []) => {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object') return [];

  for (const key of keys) {
    if (Array.isArray(payload[key])) return payload[key];
  }

  return [];
};

const COMMON_WRAPPER_KEYS = ['data', 'result', 'payload'];

const findArrayPayload = (payload, keys, seen = new Set()) => {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object' || seen.has(payload)) return null;

  seen.add(payload);
  for (const key of keys) {
    if (Array.isArray(payload[key])) return payload[key];
  }

  for (const key of [...new Set([...COMMON_WRAPPER_KEYS, ...keys])]) {
    const nested = findArrayPayload(payload[key], keys, seen);
    if (nested !== null) return nested;
  }
  return null;
};

export const normalizeRecordArrayPayload = (payload, keys = []) => (
  (findArrayPayload(payload, keys) || []).filter((record) => (
    record && typeof record === 'object' && !Array.isArray(record) && Object.keys(record).length > 0
  ))
);
