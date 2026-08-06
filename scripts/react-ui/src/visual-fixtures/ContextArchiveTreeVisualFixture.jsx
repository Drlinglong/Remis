import React from 'react';
import { Box } from '@mantine/core';

import ContextTreeV2ArchiveSummary from '../components/neologism/archiveTreeV2/ContextTreeV2ArchiveSummary';
import { publishedArchiveDemoTree } from '../components/neologism/archiveTreeV2/publishedArchiveDemoFixture';
import PublishedArchiveToolbar from '../components/neologism/PublishedArchiveToolbar';
import styles from './ContextArchiveTreeVisualFixture.module.css';

const fixtureT = (key, options) => {
    const defaults = {
        'neologism_review.court.current_project': 'Current project',
        'neologism_review.court.select_project': 'Select a project',
    };
    return defaults[key] || options?.defaultValue || key;
};

export default function ContextArchiveTreeVisualFixture() {
    return (
        <Box
            className={styles.page}
            data-remis-surface="canvas"
            data-testid="context-tree-visual-fixture"
            data-visual-ready="true"
        >
            <PublishedArchiveToolbar
                projects={[{ project_id: 'project-1', name: 'Expedition demo' }]}
                selectedProject="project-1"
                onSelectedProjectChange={() => {}}
                versions={[{ release_id: publishedArchiveDemoTree.release_id, created_at: '2026-08-05T12:00:00Z' }, { release_id: 'release-demo-2026-08-04', created_at: '2026-08-04T12:00:00Z' }]}
                currentRelease={{ release_id: publishedArchiveDemoTree.release_id, created_at: '2026-08-05T12:00:00Z' }}
                selectedReleaseId={publishedArchiveDemoTree.release_id}
                onReleaseChange={() => {}}
                projectName="Expedition demo"
                onRemoved={() => {}}
                t={fixtureT}
            />
            <ContextTreeV2ArchiveSummary tree={publishedArchiveDemoTree} mode="published" />
        </Box>
    );
}
