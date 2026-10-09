export const isRecord = (value) => Boolean(value && typeof value === 'object' && !Array.isArray(value));

export function unwrapRecordPayload(value, name) {
  if (!isRecord(value)) throw new TypeError(`Invalid ${name} response: expected an object`);
  return isRecord(value.data) ? value.data : value;
}

// Preserve a malformed response as an error, rather than turning it into an empty batch.
export function readArrayPayload(value, name) {
  if (value == null) return [];
  if (Array.isArray(value)) return value;
  if (isRecord(value)) {
    for (const key of ['items', 'data', 'result']) {
      if (Array.isArray(value[key])) return value[key];
    }
  }
  throw new TypeError(`Invalid ${name}: expected an array`);
}

export function readRecordArray(value, name) {
  const records = readArrayPayload(value, name);
  if (records.some((item) => !isRecord(item))) {
    throw new TypeError(`Invalid ${name}: expected object records`);
  }
  return records;
}
