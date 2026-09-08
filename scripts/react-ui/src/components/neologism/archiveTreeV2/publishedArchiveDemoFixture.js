import lunaPreview from './lunaContextResearchPreview.json';
import { contextResearchPreviewToArchiveTree } from './contextResearchPreviewAdapter';

export const PUBLISHED_ARCHIVE_DEMO_PROJECT_ID = lunaPreview.project.project_id;
export const PUBLISHED_ARCHIVE_DEMO_RELEASE_ID = lunaPreview.release.release_id;

export const publishedArchiveDemoProject = {
    project_id: PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    name: lunaPreview.project.name,
    label: lunaPreview.project.name,
    is_demo: true,
    is_developer_preview: true,
};

export const publishedArchiveDemoRelease = {
    release_id: PUBLISHED_ARCHIVE_DEMO_RELEASE_ID,
    project_id: PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    created_at: lunaPreview.release.created_at,
    metadata: {
        created_at: lunaPreview.release.created_at,
        analysis_config: {
            description_language: lunaPreview.provenance.description_language,
        },
        developer_preview: true,
        published: false,
        provider: lunaPreview.provenance.provider,
        model: lunaPreview.provenance.model,
        compiler: lunaPreview.provenance.compiler,
    },
};

export const publishedArchiveDemoTree = contextResearchPreviewToArchiveTree(lunaPreview);

export { lunaPreview as publishedArchiveResearchFixture };
