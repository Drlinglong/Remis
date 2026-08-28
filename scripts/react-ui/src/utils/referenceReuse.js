export const referenceEntryIdentity = (entry = {}) => [
  entry.target_lang_code || '',
  String(entry.file_path || '').replaceAll('\\', '/').toLocaleLowerCase(),
  entry.key || '',
  entry.source_text || '',
].join('\u0000');

export const referenceExclusionFromEntry = (entry = {}) => ({
  file_path: entry.file_path || '',
  key: entry.key || '',
  source_text: entry.source_text || '',
  target_lang_code: entry.target_lang_code || '',
});

export const toggleReferenceExclusion = (excludedEntries = [], entry, shouldReuse) => {
  const identity = referenceEntryIdentity(entry);
  const remaining = excludedEntries.filter(
    (candidate) => referenceEntryIdentity(candidate) !== identity,
  );
  return shouldReuse ? remaining : [...remaining, referenceExclusionFromEntry(entry)];
};
