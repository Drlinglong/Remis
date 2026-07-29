export function getProjectPrimaryAction(projectDetails) {
    if (projectDetails.status === 'archived' || projectDetails.status === 'deleted') return 'restore';
    if (Number(projectDetails.validation?.issues_count || 0) > 0) return 'fix_format';
    const translated = Number(projectDetails.overview?.translated || 0);
    const toBeProofread = Number(projectDetails.overview?.toBeProofread || 0);
    if (toBeProofread > 0) return 'proofread';
    if (translated < 100) return 'translate';
    return 'deploy';
}
