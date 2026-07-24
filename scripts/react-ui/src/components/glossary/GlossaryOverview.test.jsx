import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GlossaryOverview from './GlossaryOverview';

const navigateMock = vi.fn();

vi.mock('react-router-dom', () => ({
    useNavigate: () => navigateMock,
}));

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options) => {
            if (typeof options === 'string') return options;
            return options?.defaultValue || key;
        },
        i18n: { language: 'en' },
    }),
}));

const overview = {
    summary: {
        game_count: 2,
        glossary_count: 2,
        term_count: 42,
        bound_project_count: 1,
    },
    glossaries: [
        {
            glossary_id: 1,
            game_id: 'vic3',
            name: 'Victoria 3 Main',
            description: 'Base terminology',
            kind: 'main',
            entry_count: 40,
            bound_projects: [],
            updated_at: null,
        },
        {
            glossary_id: 2,
            game_id: 'stellaris',
            name: 'Community Project Terms',
            kind: 'project',
            entry_count: 2,
            bound_projects: [{ project_id: 'p1', name: 'Community Translation' }],
            updated_at: '2026-07-22T09:00:00',
        },
    ],
};

const renderOverview = (
    onOpenGlossary = vi.fn(),
    onDuplicateGlossary = vi.fn(),
    onPreviewBatchDelete = vi.fn(),
    onBatchDelete = vi.fn(),
    onPreviewMerge = vi.fn(),
    onStartMerge = vi.fn(),
    onStartHealthCheck = vi.fn(),
    onUpdateGlossaryMetadata = vi.fn(),
    onLoadHealthHistory = vi.fn().mockResolvedValue([]),
) => render(
    <MantineProvider>
        <GlossaryOverview
            overview={overview}
            isLoading={false}
            onOpenGlossary={onOpenGlossary}
            onDuplicateGlossary={onDuplicateGlossary}
            onUpdateGlossaryMetadata={onUpdateGlossaryMetadata}
            onPreviewBatchDelete={onPreviewBatchDelete}
            onBatchDelete={onBatchDelete}
            targetLanguages={[{ code: 'zh-CN', name_local: '中文' }]}
            apiProviders={[{
                value: 'lm_studio',
                label: 'LM Studio',
                selected_model: 'local-model',
                available_models: ['local-model'],
            }, {
                value: 'openai',
                label: 'OpenAI',
                selected_model: 'gpt-review',
                available_models: ['gpt-review', 'gpt-review-mini'],
            }]}
            projects={[
                { project_id: 'vic-project', name: 'Victoria Mod', game_id: 'vic3', status: 'active' },
                { project_id: 'p1', name: 'Community Translation', game_id: 'stellaris', status: 'active' },
                { project_id: 'p2', name: 'Second Stellaris Mod', game_id: 'stellaris', status: 'active' },
            ]}
            onPreviewMerge={onPreviewMerge}
            onStartMerge={onStartMerge}
            onStartHealthCheck={onStartHealthCheck}
            onLoadHealthHistory={onLoadHealthHistory}
        />
    </MantineProvider>
);

describe('GlossaryOverview', () => {
    beforeEach(() => {
        navigateMock.mockReset();
    });

    it('shows aggregate inventory and opens the exact glossary', () => {
        const onOpenGlossary = vi.fn();
        renderOverview(onOpenGlossary);

        expect(screen.getByText('42')).toBeInTheDocument();
        expect(screen.getByText('Victoria 3 Main')).toBeInTheDocument();
        expect(screen.getByText('Community Translation')).toBeInTheDocument();
        expect(screen.getByTestId('glossary-overview')).not.toHaveClass('mantine-ScrollArea-root');
        expect(
            screen.getByTestId('glossary-inventory-scroll')
                .querySelector('.mantine-ScrollArea-viewport')
        ).not.toBeNull();
        expect(screen.getByRole('table').querySelector('thead')).toHaveAttribute('data-sticky', 'true');

        const projectRow = screen.getByText('Community Project Terms').closest('tr');
        fireEvent.click(within(projectRow).getByRole('button', { name: 'Open glossary' }));

        expect(onOpenGlossary).toHaveBeenCalledWith(overview.glossaries[1]);
    });

    it('filters the inventory by glossary, game, or project text', () => {
        renderOverview();

        fireEvent.change(screen.getByLabelText('Find a glossary'), {
            target: { value: 'Community Translation' },
        });

        expect(screen.queryByText('Victoria 3 Main')).not.toBeInTheDocument();
        expect(screen.getByText('Community Project Terms')).toBeInTheDocument();
    });

    it('keeps selection operations visible and enables them from the current selection', () => {
        renderOverview();

        expect(screen.getByTestId('glossary-bulk-toolbar')).toBeInTheDocument();
        expect(screen.getByText('Select glossaries to use asset operations.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Duplicate glossary' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Merge selected' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Check health' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Check history' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Delete selected' })).toBeDisabled();

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));

        expect(screen.getByRole('button', { name: 'Duplicate glossary' })).toBeEnabled();
        expect(screen.getByRole('button', { name: 'Merge selected' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Check health' })).toBeEnabled();
        expect(screen.getByRole('button', { name: 'Check history' })).toBeEnabled();
        expect(screen.getByRole('button', { name: 'Delete selected' })).toBeEnabled();
    });

    it('duplicates a glossary with an explicit name and closes after success', async () => {
        const onDuplicateGlossary = vi.fn().mockResolvedValue(true);
        renderOverview(vi.fn(), onDuplicateGlossary);

        const sourceRow = screen.getByText('Victoria 3 Main').closest('tr');
        fireEvent.click(within(sourceRow).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Duplicate glossary' }));

        const nameInput = await screen.findByRole('textbox', { name: 'Copy name' });
        expect(nameInput).toHaveValue('Victoria 3 Main Copy');

        fireEvent.change(nameInput, { target: { value: 'Victoria 3 Review Copy' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create copy' }));

        await waitFor(() => {
            expect(onDuplicateGlossary).toHaveBeenCalledWith(
                overview.glossaries[0],
                'Victoria 3 Review Copy'
            );
        });
        await waitFor(() => {
            expect(screen.queryByText('Create glossary copy')).not.toBeInTheDocument();
        });
    });

    it('edits glossary name and description from a visible row action', async () => {
        const onUpdateGlossaryMetadata = vi.fn().mockResolvedValue(true);
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onUpdateGlossaryMetadata,
        );

        const sourceRow = screen.getByText('Victoria 3 Main').closest('tr');
        fireEvent.click(within(sourceRow).getByRole('button', { name: 'Edit information' }));

        const nameInput = await screen.findByRole('textbox', { name: 'Glossary name' });
        const descriptionInput = screen.getByRole('textbox', { name: 'Description' });
        expect(nameInput).toHaveValue('Victoria 3 Main');
        expect(descriptionInput).toHaveValue('Base terminology');

        fireEvent.change(nameInput, { target: { value: 'Victoria 3 Reviewed Terms' } });
        fireEvent.change(descriptionInput, {
            target: { value: 'Curated terminology for the demo mod.' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Save information' }));

        await waitFor(() => {
            expect(onUpdateGlossaryMetadata).toHaveBeenCalledWith(
                overview.glossaries[0],
                {
                    name: 'Victoria 3 Reviewed Terms',
                    description: 'Curated terminology for the demo mod.',
                    kind: 'main',
                    projectIds: [],
                }
            );
        });
        await waitFor(() => {
            expect(screen.queryByText('Edit glossary information')).not.toBeInTheDocument();
        });
    });

    it('automatically switches between project and standard types as bindings change', async () => {
        const onUpdateGlossaryMetadata = vi.fn().mockResolvedValue(true);
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onUpdateGlossaryMetadata,
        );

        const projectRow = screen.getByText('Community Project Terms').closest('tr');
        fireEvent.click(within(projectRow).getByRole('button', { name: 'Edit information' }));

        const projectInput = await screen.findByRole('textbox', { name: 'Bound projects' });
        expect(screen.getAllByText('Community Translation').length).toBeGreaterThan(0);

        fireEvent.click(projectInput);
        fireEvent.click(await screen.findByText('Second Stellaris Mod'));
        fireEvent.click(screen.getByRole('button', { name: 'Save information' }));

        await waitFor(() => {
            expect(onUpdateGlossaryMetadata).toHaveBeenCalledWith(
                overview.glossaries[1],
                expect.objectContaining({
                    kind: 'project',
                    projectIds: ['p1', 'p2'],
                })
            );
        });
    });

    it('previews destructive impact and requires main and binding confirmations', async () => {
        const impact = {
            glossary_count: 2,
            term_count: 42,
            glossaries: overview.glossaries,
            main_glossaries: [overview.glossaries[0]],
            project_glossaries: [overview.glossaries[1]],
            bound_projects: [{
                project_id: 'p1',
                project_name: 'Community Translation',
                glossary_id: 2,
                glossary_name: 'Community Project Terms',
            }],
            missing_glossary_ids: [],
        };
        const onPreviewBatchDelete = vi.fn().mockResolvedValue(impact);
        const onBatchDelete = vi.fn().mockResolvedValue(true);
        renderOverview(vi.fn(), vi.fn(), onPreviewBatchDelete, onBatchDelete);

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));
        fireEvent.click(within(screen.getByText('Community Project Terms').closest('tr')).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Delete selected' }));

        expect(await screen.findByText('Permanent deletion')).toBeInTheDocument();
        expect(onPreviewBatchDelete).toHaveBeenCalledWith([1, 2]);

        const confirmButton = screen.getByRole('button', { name: 'Delete permanently' });
        expect(confirmButton).toBeDisabled();
        fireEvent.click(screen.getByRole('checkbox', {
            name: 'I understand that {{count}} main glossaries will be deleted.',
        }));
        fireEvent.click(screen.getByRole('checkbox', {
            name: 'I understand that {{count}} project bindings will be removed and terminology consistency may be affected.',
        }));
        expect(confirmButton).toBeEnabled();
        fireEvent.click(confirmButton);

        await waitFor(() => {
            expect(onBatchDelete).toHaveBeenCalledWith([1, 2], {
                mainGlossaries: true,
                projectBindings: true,
            });
        });
    });

    it('previews a merge before starting the tracked merge task', async () => {
        const mergePreview = {
            unique_term_count: 38,
            duplicate_term_count: 3,
            conflict_count: 1,
            planned_term_count: 37,
            conflicts: [{
                normalized_source: 'admiral',
                source: 'Admiral',
                options: [
                    { glossary_name: 'Victoria 3 Main' },
                    { glossary_name: 'Community Project Terms' },
                ],
            }],
        };
        const onPreviewMerge = vi.fn().mockResolvedValue(mergePreview);
        const onStartMerge = vi.fn().mockResolvedValue({ task_id: 'merge-task' });
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onPreviewMerge,
            onStartMerge,
        );

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));
        fireEvent.click(within(screen.getByText('Community Project Terms').closest('tr')).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Merge selected' }));
        fireEvent.click(await screen.findByRole('button', { name: 'Preview merge' }));

        await waitFor(() => expect(onPreviewMerge).toHaveBeenCalledWith(
            [1, 2],
            expect.objectContaining({
                target_mode: 'new',
                conflict_strategy: 'skip_conflicts',
            })
        ));
        expect(await screen.findByText('Admiral: Victoria 3 Main / Community Project Terms')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Start merge task' }));
        await waitFor(() => expect(onStartMerge).toHaveBeenCalledWith(
            [1, 2],
            expect.objectContaining({ target_mode: 'new' })
        ));
    });

    it('starts a read-only deterministic health task for the selection', async () => {
        const onStartHealthCheck = vi.fn().mockResolvedValue({
            task_id: 'health-task',
            deterministic_preview: {
                score: 92,
                issue_count: 1,
                issues: [{ code: 'duplicate_term', severity: 'info', count: 1, message: 'Duplicates' }],
            },
        });
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onStartHealthCheck,
        );

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Check health' }));
        expect(await screen.findByText('How the check works')).toBeInTheDocument();
        expect(screen.getByText(/Uses mechanical script checks/)).toBeInTheDocument();
        fireEvent.mouseEnter(screen.getByRole('button', { name: 'How the check works' }));
        expect(await screen.findByText(/The score starts at 100/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Start health task' }));

        await waitFor(() => expect(onStartHealthCheck).toHaveBeenCalledWith(
            [1],
            expect.objectContaining({
                target_lang: 'zh-CN',
                include_ai_advice: false,
                confirm_model_usage: false,
                concurrency_limit: 1,
            })
        ));
        expect(await screen.findByText('Score 92/100')).toBeInTheDocument();
        expect(screen.getByText('Task health-task')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Start health task' })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'View task details' }));
        expect(navigateMock).toHaveBeenCalledWith('/tasks/health-task');
    });

    it('loads health-check history for the selected glossary and opens the exact task', async () => {
        const onLoadHealthHistory = vi.fn().mockResolvedValue([{
            task_id: 'previous-health-task',
            kind: 'glossary_health_check',
            status: 'completed',
            created_at: '2026-07-22T09:00:00Z',
            result: {
                types: ['glossary_health_report', 'advisory_review'],
                metadata: {
                    glossary_count: 1,
                    glossary_ids: [1],
                    score: 94,
                    issue_count: 2,
                    ai_review_status: 'completed',
                },
            },
        }]);
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onLoadHealthHistory,
        );

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Check history' }));

        await waitFor(() => expect(onLoadHealthHistory).toHaveBeenCalledWith(1));
        expect(await screen.findByText('Score 94/100')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'View task details' }));
        expect(navigateMock).toHaveBeenCalledWith('/tasks/previous-health-task');
    });

    it('defaults AI review to the configured local model and exposes concurrency', async () => {
        const onStartHealthCheck = vi.fn().mockResolvedValue({
            task_id: 'health-ai-task',
            deterministic_preview: { score: 80, issue_count: 2, issues: [] },
        });
        renderOverview(
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            vi.fn(),
            onStartHealthCheck,
        );

        fireEvent.click(within(screen.getByText('Victoria 3 Main').closest('tr')).getByRole('checkbox'));
        fireEvent.click(screen.getByRole('button', { name: 'Check health' }));
        fireEvent.click(await screen.findByRole('checkbox', {
            name: 'Add advisory AI review after deterministic checks',
        }));

        expect(screen.getByText(/Calls an LLM to suggest improvements/)).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: 'Provider' })).toHaveValue('LM Studio');
        expect(screen.getByRole('textbox', { name: 'Model' })).toHaveValue('local-model');
        expect(screen.getByRole('textbox', {
            name: 'translation_page.translation_concurrency',
        })).toHaveValue('1');

        fireEvent.click(screen.getByRole('textbox', { name: 'Provider' }));
        fireEvent.click(await screen.findByText('OpenAI'));
        expect(screen.getByRole('textbox', { name: 'Model' })).toHaveValue('gpt-review');
        expect(screen.getByRole('textbox', {
            name: 'translation_page.translation_concurrency',
        })).toHaveValue('6');

        fireEvent.click(screen.getByRole('checkbox', {
            name: /I approve this model request/,
        }));
        fireEvent.click(screen.getByRole('button', { name: 'Start health task' }));

        await waitFor(() => expect(onStartHealthCheck).toHaveBeenCalledWith(
            [1],
            expect.objectContaining({
                include_ai_advice: true,
                api_provider: 'openai',
                model_name: 'gpt-review',
                concurrency_limit: 6,
            })
        ));
    });
});
