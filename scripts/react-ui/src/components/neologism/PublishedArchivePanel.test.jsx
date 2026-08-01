import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import PublishedArchivePanel from './PublishedArchivePanel';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options) => options?.count === undefined ? key : `${key}:${options.count}`,
    }),
}));

vi.mock('../../utils/api', () => ({
    default: { get: vi.fn() },
}));

const renderPanel = (status = null) => render(
    <MantineProvider>
        <PublishedArchivePanel selectedProject="project-1" status={status} />
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
        provider_id: 'local',
        model_id: 'model-1',
        created_at: '2026-08-01T00:00:00Z',
        upstream_version: '1.2.0',
    },
};

describe('PublishedArchivePanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest') return Promise.resolve({ data: release });
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

    it('renders immutable metadata, effective overrides, and summaries without edit controls', async () => {
        renderPanel();

        expect(await screen.findByText('release-1')).toBeInTheDocument();
        expect(screen.getByText('republic')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.override_badge')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /edit|save|publish/i })).not.toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith('/api/context/releases/project-1/latest');
        expect(api.get).toHaveBeenCalledWith('/api/context/releases/release-1/effective');
        expect(api.get).not.toHaveBeenCalledWith('/api/context/releases/release-1/traceability');

        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));
        expect(await screen.findByText('text_inferred')).toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith('/api/context/releases/release-1/traceability');
    });

    it('shows the empty state when the project has no published release', async () => {
        api.get.mockRejectedValueOnce({ response: { status: 404 } });
        renderPanel();

        expect(await screen.findByTestId('mod-archive-release-empty')).toBeInTheDocument();
        expect(screen.getByText('mod_archive.release.empty_title')).toBeInTheDocument();
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
            if (url === '/api/context/releases/project-1/latest') return Promise.resolve({ data: release });
            return Promise.resolve({ data: {
                release,
                generated_synthesis: {},
                human_overrides: {},
                effective_context: {},
            } });
        });
        renderPanel();

        expect(await screen.findByTestId('mod-archive-release-partial')).toBeInTheDocument();
        expect(screen.getByText('release-1')).toBeInTheDocument();
    });

    it('reports a traceability error without adding edit controls', async () => {
        const defaultGet = api.get.getMockImplementation();
        api.get.mockImplementation((url) => (
            url.endsWith('/traceability')
                ? Promise.reject(new Error('traceability unavailable'))
                : defaultGet(url)
        ));
        renderPanel();

        await screen.findByText('release-1');
        fireEvent.click(screen.getByTestId('mod-archive-load-traceability'));

        expect(await screen.findByText('traceability unavailable')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /edit|save|publish/i })).not.toBeInTheDocument();
    });
});
