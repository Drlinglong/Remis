import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import PublishedArchivePanel from './PublishedArchivePanel';
import {
    PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    publishedArchiveDemoTree,
} from './archiveTreeV2/publishedArchiveDemoFixture';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options = {}) => options.defaultValue || (options.count === undefined ? key : `${key}:${options.count}`),
    }),
}));

vi.mock('../../utils/api', () => ({
    default: { delete: vi.fn(), get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

vi.mock('./useArchiveProjectContext', () => ({
    useArchiveProjectContext: ({ selectedProject }) => ({
        projects: [{ project_id: 'project-1', name: 'Demo mod' }],
        currentProject: selectedProject ? { project_id: selectedProject, name: 'Demo mod' } : null,
        projectGlossary: null,
        terminologyIndex: new Map(),
    }),
}));

const onSelectedProjectChange = vi.fn();
const demoTree = { ...publishedArchiveDemoTree, project_id: 'project-1' };
const release = {
    release_id: demoTree.release_id,
    project_id: 'project-1',
    metadata: { created_at: '2026-08-05T12:00:00Z' },
    versions: [
        { release_id: demoTree.release_id, created_at: '2026-08-05T12:00:00Z' },
        { release_id: 'release-demo-2026-08-04', created_at: '2026-08-04T12:00:00Z' },
    ],
};

const renderPanel = (selectedProject = 'project-1') => render(
    <MantineProvider>
        <PublishedArchivePanel
            selectedProject={selectedProject}
            onSelectedProjectChange={onSelectedProjectChange}
        />
    </MantineProvider>,
);

describe('PublishedArchivePanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.delete.mockResolvedValue({ data: { status: 'removed' } });
        api.get.mockImplementation((url) => {
            if (url === '/api/context/releases/project-1/latest?optional=true') return Promise.resolve({ data: release });
            if (url === `/api/context/tree-v2/projects/project-1/latest-release`) return Promise.resolve({ data: demoTree });
            if (url === `/api/context/tree-v2/projects/project-1/releases/${demoTree.release_id}`) return Promise.resolve({ data: demoTree });
            if (url === '/api/context/releases/release-demo-2026-08-04') return Promise.resolve({ data: { ...release, release_id: 'release-demo-2026-08-04' } });
            if (url.endsWith('/effective')) return Promise.resolve({ data: { effective_context: { 'project:summary': { summary: 'demo' } } } });
            throw new Error(`Unexpected GET ${url}`);
        });
    });

    it('renders the new map page without glossary navigation or the old advanced wall', async () => {
        renderPanel();

        expect(await screen.findByTestId('published-archive-workbench')).toBeInTheDocument();
        expect(screen.getByTestId('published-archive-toolbar')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-map')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-entities')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Delete archive data' })).toBeInTheDocument();
        expect(screen.queryByTestId('mod-archive-advanced-toggle')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'neologism_review.court.inspect_project_glossary' })).not.toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith('/api/context/tree-v2/projects/project-1/latest-release');
    });

    it('exposes the local demo project in the real published-page selector', async () => {
        renderPanel();

        const projectSelect = screen.getByRole('textbox', { name: 'neologism_review.court.current_project' });
        fireEvent.mouseDown(projectSelect);

        expect(await screen.findByText('星港远征：失落航道（演示项目）')).toBeInTheDocument();
    });

    it('renders the demo project without requesting or deleting backend archive data', async () => {
        renderPanel(PUBLISHED_ARCHIVE_DEMO_PROJECT_ID);

        expect(await screen.findByTestId('published-context-map')).toBeInTheDocument();
        expect(screen.getAllByText('星港远征：失落航道').length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: 'Delete archive data' })).toBeDisabled();
        expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining(PUBLISHED_ARCHIVE_DEMO_PROJECT_ID));
        fireEvent.click(screen.getByTestId('mod-archive-remove'));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        expect(api.delete).not.toHaveBeenCalled();
    });

    it('switches archive versions through the explicit release and tree endpoints', async () => {
        renderPanel();
        await screen.findByTestId('published-context-map');

        const versionSelect = screen.getByRole('textbox', { name: 'Archive version' });
        fireEvent.mouseDown(versionSelect);
        fireEvent.click(await screen.findByText(/release-demo-2026-08-04/));

        await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/context/releases/release-demo-2026-08-04'));
        await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/context/tree-v2/projects/project-1/releases/release-demo-2026-08-04'));
    });

    it('opens the selected card detail and requires confirmation before deletion', async () => {
        renderPanel();
        await screen.findByTestId('published-context-map');

        fireEvent.click(screen.getByTestId('published-context-fragment-fragment-signal'));
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('解读求救讯号');
        expect(screen.getByTestId('published-context-detail')).toHaveTextContent('events/starport_expedition.yml:27');

        fireEvent.click(screen.getByTestId('mod-archive-remove'));
        expect(await screen.findByRole('dialog')).toHaveTextContent('Demo mod');
        fireEvent.click(screen.getByTestId('mod-archive-confirm-remove'));
        await waitFor(() => expect(api.delete).toHaveBeenCalledWith(
            '/api/context/projects/project-1/archive',
            { data: { project_name: 'Demo mod', approved: true } },
        ));
    });
});
