import { readRecordArray, unwrapRecordPayload } from './workflowPayload';

export function normalizePreScanResults(value) {
  try {
    const data = unwrapRecordPayload(value, 'pre-scan');
    return { ...data, file_summaries: readRecordArray(data.file_summaries, 'file_summaries').map((file) => ({
      ...file, dirty_entries: readRecordArray(file.dirty_entries, 'dirty_entries'),
    })) };
  } catch (error) {
    return { file_summaries: [], payloadError: error.message };
  }
}
