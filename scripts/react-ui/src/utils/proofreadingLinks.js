export const buildProofreadingUrl = ({
    projectId,
    fileId,
    entryKey,
    lineHint,
    issueId,
    taskId,
} = {}) => {
    const params = new URLSearchParams();
    if (projectId) params.set('projectId', projectId);
    if (fileId) params.set('fileId', fileId);
    if (entryKey) params.set('entryKey', entryKey);
    if (lineHint) params.set('lineHint', String(lineHint));
    if (issueId) params.set('issueId', issueId);
    if (taskId) params.set('taskId', taskId);
    const query = params.toString();
    return query ? `/proofreading?${query}` : '/proofreading';
};
