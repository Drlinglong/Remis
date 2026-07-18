import { describe, expect, it } from 'vitest';
import {
  clearProofreadingSession,
  createProofreadingSessionSnapshot,
  readProofreadingSession,
  restoreProofreadingRows,
  writeProofreadingSession,
} from './proofreadingSession';

const createStorage = () => {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
};

describe('proofreadingSession', () => {
  it('stores only changed patches plus bounded UI state', () => {
    const snapshot = createProofreadingSessionSnapshot({
      fileInfo: { project_id: 'project-1', file_id: 'file-1' },
      documentRevision: 'revision-1',
      rows: [
        { entry_id: 'entry-0', key: 'a', row_type: 'translation', editable: true, baseline_value: 'A', final_value: 'A' },
        { entry_id: 'entry-1', key: 'b', row_type: 'translation', editable: true, baseline_value: 'B', final_value: 'Edited' },
      ],
      query: 'search',
      filter: 'changed',
      focusedEntryKey: 'b',
      scrollOffset: 120,
    });

    expect(snapshot.patches).toEqual([{
      entry_id: 'entry-1',
      key: 'b',
      row_type: 'translation',
      final_value: 'Edited',
    }]);
    expect(snapshot.scrollOffset).toBe(120);
  });

  it('round-trips and clears a versioned session snapshot', () => {
    const storage = createStorage();
    expect(writeProofreadingSession({ projectId: 'p' }, storage)).toBe(true);
    expect(readProofreadingSession(storage).projectId).toBe('p');
    clearProofreadingSession(storage);
    expect(readProofreadingSession(storage)).toBeNull();
  });

  it('never applies patches across document revisions', () => {
    const rows = [{ entry_id: 'entry-0', row_type: 'translation', key: 'a', final_value: 'Disk' }];
    const result = restoreProofreadingRows({
      rows,
      documentRevision: 'new',
      snapshot: {
        documentRevision: 'old',
        patches: [{ entry_id: 'entry-0', row_type: 'translation', key: 'a', final_value: 'Draft' }],
      },
    });
    expect(result.status).toBe('conflict');
    expect(result.rows[0].final_value).toBe('Disk');
  });
});
