import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import { formatContextSchemaVersion } from './PublishedArchiveContent';
import PublishedArchivePanel from './PublishedArchivePanel';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options) => options?.count === undefined ? key : `${key}:${options.count}`,
    }),
}));

vi.mock('../../utils/api', () => ({
    default: { delete: vi.fn(), get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

const onSelectedProjectChange = vi.fn();
const onOpenGlossary = vi.fn();

const renderPanel = (status = null) => render(
    <MantineProvider>
        <PublishedArchivePanel
            selectedProject="project-1"
            onSelectedProjectChange={onSelectedProjectChange}
            onOpenGlossary={onOpenGlossary}
            status={status}
        />
    </MantineProvider>,
);

const release = {
    release_id: 'release-1',
    project_id: 'project-1',
    metadata: {
        source_snapshot_hash: 'snapshot-1',
        analysis_scope: { mode: 'narrative_context', files: ['common/characters.txt'] },
        schema_version: 'context-v1',
        prompt_version: 'context-synthesis-v1',
        analysis_config: { description_language: 'zh-CN', temperature: 0 },
        prompt_example: 'System message:\nUse grounded evidence.\n\nUser message:\nExample source text.',
        provider_id: 'local',
        model_id: 'model-1',
        created_at: '2026-08-01T00:00:00Z',
        upstream_version: '1.2.0',
    },
};

describe('PublishedArchivePanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.post.mockResolvedValue({ data: {} });
        api.put.mockResolvedValue({ data: {} });
        api.delete.mockResolvedValue({ data: { status: 'removed' } });
        api.get.mockImplementation((url) => {
            if (url === '/api/projects') return Promise.resolve({ data: [{ project_id: 'project-1', name: 'Demo', game_id: 'stellaris' }] });
            if (url === '/api/neologisms/project-glossary/project-1') return Promise.resolve({ data: { glossary_id: 7, name: 'Demo terminology', game_id: 'stellaris' } });
            if (url === '/api/neologisms?project_id=project-1') return Promise.resolve({ data: [{ original: 'Republic', suggestion: '共和国候选', status: 'pending' }] });
            if (url === '/api/glossary/content?glossary_id=7&page=1&pageSize=250') return Promise.resolve({ data: { entries: [], totalCount: 0 } });
            if (url === '/api/context/releases/project-1/latest?optional=true') return Promise.resolve({ data: release });
            if (url === '/api/context/releases/release-1/effective') {
                return Promise.resolve({ data: {
                    release,
                    generated_synthesis: { 'entity:republic': { summary: 'A state' } },
                    human_overrides: { 'entity:republic': { preferred_name: '共和国' } },
                    effective_context: {
                        'project:summary': { summary: 'A project summary' },
                        'entity:republic': { summary: 'A state', preferred_name: '共和国' },
                        'event:war': { summary: 'A conflict' },
                    },
                    aggregate_metadata: {
                        'entity:republic': {
                            candidate_kind: 'entity', tier: 'core', mention_count: 9,
                            event_chain_coverage: 3,
                        },
                    },
                } });
            }
            if (url === '/api/context/releases/release-1/traceability') {
                return Promise.resolve({ data: [{
                    aggregate: { aggregate_key: 'entity:republic', aggregate_type: 'entity' },
                    contributions: [{
                        contribution: { contribution_type: 'fact', provenance: 'text_inferred' },
                        source_item: { source_ref: 'common/characters.txt::1:republic', content: 'The Republic' },
                    }],
                }] });
            }
            throw new Error(`Unexpected GET ${url}`);
        });
    });

    it('derives a readable semantic label from future context schema revisions', () => {
        expect(formatContextSchemaVersion('context-v2')).toBe('v0.0.2');
        expect(formatContextSchemaVersion('context-v27')).toBe('v0.0.27');
        expect(formatContextSchemaVersion('custom-schema')).toBe('custom-schema');
    });

    it('renders immutable metadata, effective overrides, and summaries without edit controls', async () => {
        renderPanel();

        expect(await screen.findByText('A project summary')).toBeInTheDocument();
        expect(screen.queryByTestId('mod-archive-metadata-details')).not.toBeInTheDocument();
        fireEvent.click(screen.getByTestId('mod-archive-advanced-toggle'));
        const metadataDetails = screen.getByTestId('mod-archive-metadata-details');
        expect(metadataDetails).not.toHaveAttribute('open');
        expect(screen.getByText('v0.0.1')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.analysis_scopes.narrative_context')).toBeInTheDocument();
        expect(screen.queryByText('context-synthesis-v1')).not.toBeInTheDocument();
        expect(screen.queryByText(/"description_language": "zh-CN"/)).not.toBeInTheDocument();
        expect(screen.getByTestId('mod-archive-prompt-example')).toHaveTextContent('System message:');
        expect(screen.getByTestId('mod-archive-prompt-example')).toHaveTextContent('User message:');
        expect(screen.getByText(/2026-08-01 \d{2}:00/)).toBeInTheDocument();
        expect(screen.getByText('local')).toBeInTheDocument();
        expect(screen.getByText('model-1')).toBeInTheDocument();
        expect(screen.queryByText('summary')).not.toBeInTheDocument();
        expect(screen.getByText('republic（共和国候选）')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.override_badge')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.candidate_tier.core')).toBeInTheDocument();
        expect(screen.getByText(/mention_count.*9/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /edit|save|publish/i })).not.toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith(
            '/api/context/releases/project-1/latest?optional=true',
        );
        expect(api.get).toHaveBeenCalledWith('/api/context/releases/release-1/effective');
        expect(api.get).not.toHaveBeenCalledWith('/api/context/releases/release-1/traceability');

        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));
        expect(await screen.findByText('mod_archive.release.provenance.text_inferred')).toBeInTheDocument();
        const evidenceGroup = screen.getAllByText('republic（共和国候选）')
            .find((node) => node.tagName === 'SPAN')
            .closest('details');
        expect(evidenceGroup).not.toHaveAttribute('open');
        expect(screen.getByText('mod_archive.release.evidence_membership_count:1')).toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith('/api/context/releases/release-1/traceability');
    });

    it('orders summary and evidence sections as project, event, then entity', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/release-1/traceability') {
                return Promise.resolve({ data: [
                    {
                        aggregate: { aggregate_key: 'entity:republic', aggregate_type: 'entity' },
                        contributions: [{
                            contribution: { contribution_type: 'fact', provenance: 'text_inferred' },
                            source_item: { source_ref: 'entity.yml::republic', content: 'The Republic' },
                        }],
                    },
                    {
                        aggregate: { aggregate_key: 'project:summary', aggregate_type: 'project' },
                        contributions: [{
                            contribution: { contribution_type: 'fact', provenance: 'text_inferred' },
                            source_item: { source_ref: 'project.yml::intro', content: 'A project' },
                        }],
                    },
                    {
                        aggregate: { aggregate_key: 'event:war', aggregate_type: 'event' },
                        contributions: [{
                            contribution: { contribution_type: 'event', provenance: 'text_inferred' },
                            source_item: { source_ref: 'events.yml::war', content: 'A war' },
                        }],
                        delivery_membership: { count: 12, role_counts: { primary_member: 12 } },
                    },
                ] });
            }
            return defaultGet(url);
        });
        renderPanel();

        await screen.findByText('A project summary');
        const summaryHeadings = screen.getAllByRole('heading', { level: 4 }).slice(0, 3);
        expect(summaryHeadings.map((node) => node.textContent)).toEqual([
            'mod_archive.release.project_summary',
            'mod_archive.release.event_summary:1',
            'mod_archive.release.entity_summary:1',
        ]);

        fireEvent.click(screen.getByTestId('mod-archive-advanced-toggle'));
        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));
        await screen.findByText('project.yml::intro');
        const traceability = screen.getByTestId('mod-archive-traceability');
        const evidenceHeadings = Array.from(traceability.querySelectorAll('h4'));
        expect(evidenceHeadings.map((node) => node.textContent)).toEqual([
            'mod_archive.release.project_summary:1',
            'mod_archive.release.event_summary:1',
            'mod_archive.release.entity_summary:1',
        ]);
        expect(screen.getByText('mod_archive.release.delivery_membership_count:12')).toBeInTheDocument();
    });

    it('shows project context, glossary navigation, and pending terminology without claiming approval', async () => {
        renderPanel();

        expect(await screen.findByText('republic（共和国候选）')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.term_status.suggested')).toBeInTheDocument();
        expect(screen.getByText('Demo terminology')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', {
            name: 'neologism_review.court.inspect_project_glossary',
        }));
        expect(onOpenGlossary).toHaveBeenCalledWith({ glossaryId: 7, gameId: 'stellaris' });
    });

    it('keeps audit-only candidates out of effective entity summaries', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/release-1/traceability') {
                return Promise.resolve({ data: [{
                    aggregate: {
                        aggregate_key: 'entity:audit-only',
                        aggregate_type: 'entity',
                        canonical_display_name: 'Audit-only concept',
                        normalized_match_key: 'audit-only concept',
                        aliases: ['Audit-only concept'],
                        candidate_kind: 'incidental_concept',
                        tier: 'core',
                        audit_only: true,
                    },
                    contributions: [{ source_item: { source_ref: 'audit::1', content: 'An incidental concept' } }],
                }] });
            }
            return defaultGet(url);
        });
        renderPanel();

        await screen.findByText('A state');
        const summaryEntityHeading = screen.getAllByRole('heading', { level: 4 })
            .find((node) => node.textContent === 'mod_archive.release.entity_summary:1');
        const summaryEntitySection = summaryEntityHeading.closest('section');
        expect(summaryEntitySection).not.toHaveTextContent('Audit-only concept');

        fireEvent.click(screen.getByTestId('mod-archive-advanced-toggle'));
        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));
        expect(await screen.findByTestId('mod-archive-candidate-incidental-0')).toHaveTextContent(
            'Audit-only concept',
        );
        expect(screen.getByTestId('mod-archive-candidate-audit')).not.toHaveAttribute('open');
    });

    it('removes the selected project archive only after explicit confirmation', async () => {
        renderPanel();

        fireEvent.click(await screen.findByTestId('mod-archive-remove'));
        expect(await screen.findByRole('dialog')).toHaveTextContent('Demo');
        fireEvent.click(screen.getByTestId('mod-archive-confirm-remove'));

        await waitFor(() => expect(api.delete).toHaveBeenCalledWith(
            '/api/context/projects/project-1/archive',
            { data: { project_name: 'Demo', approved: true } },
        ));
    });

    it('shows the empty state when the project has no published release', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest?optional=true') {
                return Promise.resolve({ data: { release: null } });
            }
            if (url === '/api/context/projects/project-1/analysis-preview?optional=true') {
                return Promise.resolve({ data: { preview: null } });
            }
            return defaultGet(url);
        });
        renderPanel();

        expect(await screen.findByTestId('mod-archive-release-empty')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.empty_title')).toBeInTheDocument();
    });

    it('previews persisted entities and event chains when publication failed', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest?optional=true') {
                return Promise.resolve({ data: { release: null } });
            }
            if (url === '/api/context/projects/project-1/analysis-preview?optional=true') {
                return Promise.resolve({ data: {
                    project_id: 'project-1',
                    published: false,
                    warning_code: 'unpublished_analysis_preview',
                    run: {
                        run_id: 'run-failed',
                        status: 'failed',
                        provider_id: 'openrouter',
                        model_id: 'openai/gpt-5.6-luna',
                    },
                    counts: {
                        entities: 2,
                        events: 1,
                        entity_summaries: 1,
                        event_summaries: 1,
                    },
                    entries: [{
                        aggregate_id: 'entity-1',
                        aggregate_key: 'entity:toxic god',
                        aggregate_type: 'entity',
                        label: 'Toxic God',
                        summary: 'A recurring godlike toxic entity.',
                        payload: {
                            candidate_kind: 'entity',
                            tier: 'core',
                            aliases: ['The Toxic God'],
                            mention_count: 8,
                            source_item_coverage: 4,
                            local_unit_coverage: 4,
                            event_chain_coverage: 2,
                            summary_eligible: true,
                        },
                    }, {
                        aggregate_id: 'entity-2',
                        aggregate_key: 'entity:field equations',
                        aggregate_type: 'entity',
                        label: 'advanced field equations',
                        summary: null,
                        payload: {
                            candidate_kind: 'incidental_concept',
                            tier: 'incidental',
                            aliases: [],
                            audit_only: true,
                        },
                    }, {
                        aggregate_id: 'event-1',
                        aggregate_key: 'event:chain_toxic_god',
                        aggregate_type: 'event',
                        label: 'chain_toxic_god',
                        summary: 'The order begins its quest.',
                        payload: {
                            event: 'The Toxic God visits the homeworld.',
                            consequence: 'The order is founded.',
                            participants: ['Toxic God', 'Order'],
                            delivery_coverage: { local_unit_coverage: 12 },
                        },
                    }],
                } });
            }
            return defaultGet(url);
        });
        renderPanel();

        expect(await screen.findByTestId('mod-archive-analysis-preview')).toBeInTheDocument();
        expect(screen.getByText('Toxic God')).toBeInTheDocument();
        expect(screen.getByText('A recurring godlike toxic entity.')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.preview.warning_title')).toBeInTheDocument();
        expect(screen.queryByTestId('mod-archive-start-draft')).not.toBeInTheDocument();

        expect(screen.getByText('The Toxic God visits the homeworld.')).toBeInTheDocument();
        expect(screen.getByText('The order begins its quest.')).toBeInTheDocument();
        expect(screen.queryByText('advanced field equations')).not.toBeInTheDocument();

        fireEvent.click(screen.getByTestId('mod-archive-preview-advanced-toggle'));
        fireEvent.click(screen.getByText('mod_archive.release.preview.event_tab:1'));
        expect(await screen.findByText('chain_toxic_god')).toBeInTheDocument();
    });

    it('shows an error state for unavailable release metadata', async () => {
        api.get.mockRejectedValueOnce(new Error('network unavailable'));
        renderPanel();

        expect(await screen.findByTestId('mod-archive-release-error')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'mod_archive.release.retry' })).toBeInTheDocument();
    });

    it('marks a readable release stale when the current source hash changed', async () => {
        renderPanel({ sourceSnapshotHash: 'snapshot-current' });

        await waitFor(() => expect(screen.getByTestId('mod-archive-release-stale')).toBeInTheDocument());
        expect(screen.getByTestId('mod-archive-release-panel')).toBeInTheDocument();
    });

    it('keeps metadata visible while reporting a partial effective summary', async () => {
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest?optional=true') return Promise.resolve({ data: release });
            return Promise.resolve({ data: {
                release,
                generated_synthesis: {},
                human_overrides: {},
                effective_context: {},
            } });
        });
        renderPanel();

        expect(await screen.findByTestId('mod-archive-release-partial')).toBeInTheDocument();
        expect(screen.getByText('local')).toBeInTheDocument();
    });

    it('reports a traceability error without adding edit controls', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => (
            url.endsWith('/traceability')
                ? Promise.reject(new Error('traceability unavailable'))
                : defaultGet(url)
        ));
        renderPanel();

        await screen.findByText('A project summary');
        fireEvent.click(screen.getByTestId('mod-archive-advanced-toggle'));
        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));

        expect(await screen.findByText('traceability unavailable')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /edit|save|publish/i })).not.toBeInTheDocument();
    });

    it('starts a draft, saves a bounded override, confirms publish, and refreshes to the child release', async () => {
        const inheritedDraft = {
            draft_id: 'draft-1',
            project_id: 'project-1',
            base_release_id: 'release-1',
            status: 'draft',
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:00:00Z',
            overrides: [{
                target_key: 'entity:republic',
                value: { preferred_name: '共和国', legacy_alias: 'preserved-but-not-editable' },
                note: 'Inherited from the previous release',
            }],
        };
        const savedDraft = {
            ...inheritedDraft,
            overrides: [{
                ...inheritedDraft.overrides[0],
                value: {
                    preferred_name: 'The Republic',
                    legacy_alias: 'preserved-but-not-editable',
                },
            }],
        };
        const childRelease = {
            ...release,
            release_id: 'release-2',
            metadata: { ...release.metadata, parent_release_id: 'release-1' },
        };
        let latestCalls = 0;
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest?optional=true') {
                latestCalls += 1;
                return Promise.resolve({ data: latestCalls === 1 ? release : childRelease });
            }
            if (url === '/api/context/releases/release-1/effective') {
                return Promise.resolve({ data: {
                    release,
                    generated_synthesis: { 'entity:republic': { summary: 'A state' } },
                    human_overrides: {},
                    effective_context: { 'entity:republic': { summary: 'A state' } },
                } });
            }
            if (url === '/api/context/releases/release-2/effective') {
                return Promise.resolve({ data: {
                    childRelease,
                    generated_synthesis: { 'entity:republic': { summary: 'A state' } },
                    human_overrides: { 'entity:republic': { preferred_name: 'The Republic' } },
                    effective_context: { 'entity:republic': { summary: 'A state', preferred_name: 'The Republic' } },
                } });
            }
            throw new Error(`Unexpected GET ${url}`);
        });
        api.post.mockImplementation((url) => {
            if (url === '/api/context/projects/project-1/releases/release-1/drafts') {
                return Promise.resolve({ data: inheritedDraft });
            }
            if (url === '/api/context/projects/project-1/drafts/draft-1/publish') {
                return Promise.resolve({ data: childRelease });
            }
            throw new Error(`Unexpected POST ${url}`);
        });
        api.put.mockResolvedValue({ data: savedDraft });

        renderPanel();
        await screen.findByText('A state');
        fireEvent.click(screen.getByTestId('mod-archive-start-draft'));

        expect(await screen.findByTestId('mod-archive-draft-editor')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.draft.inherited_badge')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.draft.unknown_title')).toBeInTheDocument();
        expect(screen.getByText('entity:republic · legacy_alias')).toBeInTheDocument();
        fireEvent.change(screen.getByTestId('mod-archive-draft-field-preferred_name'), {
            target: { value: 'The Republic' },
        });
        fireEvent.click(screen.getByTestId('mod-archive-save-override'));
        await waitFor(() => expect(api.put).toHaveBeenCalledWith(
            '/api/context/projects/project-1/drafts/draft-1/overrides',
            expect.objectContaining({
                context_key: 'entity:republic',
                value: {
                    preferred_name: 'The Republic',
                    legacy_alias: 'preserved-but-not-editable',
                },
                note: 'Inherited from the previous release',
            }),
        ));
        expect(await screen.findByText('mod_archive.release.draft.save_success')).toBeInTheDocument();

        fireEvent.click(screen.getByTestId('mod-archive-open-publish'));
        expect(await screen.findByTestId('mod-archive-publish-modal')).toBeInTheDocument();
        expect(await screen.findByText('mod_archive.release.draft.publish_base')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('mod-archive-publish-confirm'));

        expect(await screen.findByTestId('mod-archive-published-notice')).toBeInTheDocument();
        expect(screen.getAllByText('release-2').length).toBeGreaterThan(0);
        expect(api.post).toHaveBeenCalledWith('/api/context/projects/project-1/drafts/draft-1/publish');
        expect(api.get.mock.calls.filter(([url]) => url === '/api/context/releases/project-1/latest?optional=true')).toHaveLength(2);
        fireEvent.click(screen.getByTestId('mod-archive-advanced-toggle'));
        expect(screen.getByText('release-1')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.parent_release')).toBeInTheDocument();
        expect(screen.queryByTestId('mod-archive-draft-editor')).not.toBeInTheDocument();
    });
});
