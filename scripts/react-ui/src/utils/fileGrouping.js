import { toParadoxLang } from './paradoxMapping';

/**
 * Groups files into sources and targets based on Paradox naming conventions.
 * 
 * @param {Array} files - Flat list of files from the database.
 * @param {Object} selectedProject - The current project object.
 * @returns {Object} { sources: Array, targetsMap: Object }
 */
export const groupFiles = (files, selectedProject) => {
    if (!selectedProject || !files) return { sources: [], targetsMap: {} };

    // Strict Source Identification based on Project Settings
    const dbLang = selectedProject.source_language || 'english';
    const paradoxLang = toParadoxLang(dbLang);


    const sources = [];
    const targetsMap = {};
    const sourceBaseMap = {};

    const getFileName = (path) => path.replace(/\\/g, '/').split('/').pop();

    // Pass 1: Identify REAL Sources based on filename pattern
    // Allows _l_english.yml OR  l_english.yml (space separator commonly used in CN mods)
    const suffixRegex = new RegExp(`[\\s_]l_${paradoxLang}\\.yml$`, 'i');

    files.forEach(f => {
        const fileName = getFileName(f.file_path);
        // Check regex match
        if (suffixRegex.test(fileName)) {
            sources.push(f);

            // Extract base name by removing the matched suffix
            // We can't just slice fixed length because suffix length varies (space vs underscore)
            const match = fileName.match(suffixRegex);
            const suffixLength = match[0].length;
            const baseName = fileName.slice(0, -suffixLength);

            sourceBaseMap[baseName.toLowerCase()] = f;
            targetsMap[f.file_id] = [];
        }
    });

    // Pass 2: Identify Targets (everything that is NOT a source)
    files.forEach(f => {
        // Skip if it was already identified as source
        if (sources.includes(f)) return;

        const fileName = getFileName(f.file_path);

        // Try to match against known source bases
        for (const baseLower in sourceBaseMap) {
            // Updated: Use regex to detect translation files, supporting both space and underscore separators
            // Matches: "{base}_l_{otherLang}.yml" OR "{base} l_{otherLang}.yml"
            const targetRegex = new RegExp(`^${baseLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s_]l_\\w+\\.yml$`, 'i');
            if (targetRegex.test(fileName.toLowerCase())) {
                // Ensure it belongs to THIS source file's group
                targetsMap[sourceBaseMap[baseLower].file_id].push(f);
                break; // One file belongs to one source
            }
        }
    });

    return { sources, targetsMap };
};
