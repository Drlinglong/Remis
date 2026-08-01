import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Alert,
    Badge,
    Button,
    Checkbox,
    Group,
    Modal,
    MultiSelect,
    Paper,
    ScrollArea,
    Select,
    SimpleGrid,
    Stack,
    Table,
    Text,
    TextInput,
    Textarea,
    Title,
} from '@mantine/core';
import {
    IconAlertTriangle,
    IconBook2,
    IconCopy,
    IconInfoCircle,
    IconSearch,
    IconTrash,
} from '@tabler/icons-react';

import { usePersistentState } from '../../hooks/usePersistentState';
import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../utils/localizedDateTime';
import styles from './GlossaryOverview.module.css';
import GlossaryOperations from './GlossaryOperations';
import GlossaryRowActions from './GlossaryRowActions';

const KIND_COLORS = {
    main: 'blue',
    project: 'grape',
    standard: 'gray',
};

const formatUpdatedAt = (value, fallback, language) => {
    if (!value) return fallback;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return fallback;
    return formatLocalizedDateTime(date, language, { dateStyle: 'short' });
};

const GlossaryOverview = ({
    overview,
    isLoading,
    isMutating = false,
    onOpenGlossary,
    onDuplicateGlossary,
    onUpdateGlossaryMetadata,
    onPreviewBatchDelete,
    onBatchDelete,
    targetLanguages,
    apiProviders,
    projects = [],
    operation,
    onPreviewMerge,
    onStartMerge,
    onStartHealthCheck,
    onLoadHealthHistory,
}) => {
    const { t, i18n } = useTranslation();
    const [query, setQuery] = usePersistentState('glossary_overview_query', '');
    const [kind, setKind] = usePersistentState('glossary_overview_kind', 'all');
    const [duplicateTarget, setDuplicateTarget] = useState(null);
    const [duplicateName, setDuplicateName] = useState('');
    const [duplicateNameError, setDuplicateNameError] = useState('');
    const [editTarget, setEditTarget] = useState(null);
    const [editName, setEditName] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [editKind, setEditKind] = useState('standard');
    const [editProjectIds, setEditProjectIds] = useState([]);
    const [editNameError, setEditNameError] = useState('');
    const [editProjectError, setEditProjectError] = useState('');
    const [selectedIds, setSelectedIds] = useState([]);
    const [deleteImpact, setDeleteImpact] = useState(null);
    const [confirmMainGlossaries, setConfirmMainGlossaries] = useState(false);
    const [confirmProjectBindings, setConfirmProjectBindings] = useState(false);
    const summary = overview?.summary || {};

    useEffect(() => {
        const availableIds = new Set(
            (overview?.glossaries || []).map((glossary) => glossary.glossary_id)
        );
        setSelectedIds((current) => current.filter((id) => availableIds.has(id)));
    }, [overview?.glossaries]);

    const openDuplicateDialog = (glossary) => {
        setDuplicateTarget(glossary);
        setDuplicateName(
            `${glossary.name} ${t('glossary_duplicate_copy_suffix', 'Copy')}`
        );
        setDuplicateNameError('');
    };

    const closeDuplicateDialog = () => {
        if (isMutating) return;
        setDuplicateTarget(null);
        setDuplicateName('');
        setDuplicateNameError('');
    };

    const confirmDuplicate = async () => {
        const normalizedName = duplicateName.trim();
        if (!normalizedName) {
            setDuplicateNameError(t('glossary_duplicate_name_required', 'Enter a name for the copy.'));
            return;
        }

        const success = await onDuplicateGlossary(duplicateTarget, normalizedName);
        if (success) closeDuplicateDialog();
    };

    const openEditDialog = (glossary) => {
        setEditTarget(glossary);
        setEditName(glossary.name || '');
        setEditDescription(glossary.description || '');
        setEditKind(glossary.kind || 'standard');
        setEditProjectIds(
            (glossary.bound_projects || []).map((project) => project.project_id)
        );
        setEditNameError('');
        setEditProjectError('');
    };

    const closeEditDialog = () => {
        if (isMutating) return;
        setEditTarget(null);
        setEditName('');
        setEditDescription('');
        setEditKind('standard');
        setEditProjectIds([]);
        setEditNameError('');
        setEditProjectError('');
    };

    const confirmEdit = async () => {
        const normalizedName = editName.trim();
        if (!normalizedName) {
            setEditNameError(t('glossary_duplicate_name_required', 'Enter a glossary name.'));
            return;
        }
        if (editKind === 'project' && editProjectIds.length === 0) {
            setEditProjectError(
                t('glossary_edit_metadata_project_required', 'Select at least one project.')
            );
            return;
        }

        const success = await onUpdateGlossaryMetadata(editTarget, {
            name: normalizedName,
            description: editDescription.trim(),
            kind: editKind,
            projectIds: editProjectIds,
        });
        if (success) closeEditDialog();
    };

    const filteredGlossaries = useMemo(() => {
        const glossaries = overview?.glossaries || [];
        const normalizedQuery = query.trim().toLocaleLowerCase();
        return glossaries.filter((glossary) => {
            if (kind !== 'all' && glossary.kind !== kind) return false;
            if (!normalizedQuery) return true;

            const projectNames = (glossary.bound_projects || [])
                .map((project) => `${project.name || ''} ${project.project_id || ''}`)
                .join(' ');
            return [glossary.name, glossary.game_id, glossary.description, projectNames]
                .filter(Boolean)
                .some((value) => value.toLocaleLowerCase().includes(normalizedQuery));
        });
    }, [kind, overview?.glossaries, query]);

    const visibleIds = filteredGlossaries.map((glossary) => glossary.glossary_id);
    const allVisibleSelected = visibleIds.length > 0
        && visibleIds.every((id) => selectedIds.includes(id));
    const someVisibleSelected = visibleIds.some((id) => selectedIds.includes(id));
    const selectedGlossaries = (overview?.glossaries || []).filter((glossary) => (
        selectedIds.includes(glossary.glossary_id)
    ));
    const singleSelectedGlossary = selectedGlossaries.length === 1
        ? selectedGlossaries[0]
        : null;

    const toggleAllVisible = (checked) => {
        setSelectedIds((current) => {
            if (checked) return Array.from(new Set([...current, ...visibleIds]));
            const visibleSet = new Set(visibleIds);
            return current.filter((id) => !visibleSet.has(id));
        });
    };

    const toggleGlossary = (glossaryId, checked) => {
        setSelectedIds((current) => (
            checked
                ? Array.from(new Set([...current, glossaryId]))
                : current.filter((id) => id !== glossaryId)
        ));
    };

    const openBatchDeletePreview = async () => {
        const impact = await onPreviewBatchDelete(selectedIds);
        if (!impact) return;
        setDeleteImpact(impact);
        setConfirmMainGlossaries(false);
        setConfirmProjectBindings(false);
    };

    const closeBatchDelete = () => {
        if (isMutating) return;
        setDeleteImpact(null);
        setConfirmMainGlossaries(false);
        setConfirmProjectBindings(false);
    };

    const confirmBatchDelete = async () => {
        const success = await onBatchDelete(selectedIds, {
            mainGlossaries: confirmMainGlossaries,
            projectBindings: confirmProjectBindings,
        });
        if (success) {
            setSelectedIds([]);
            closeBatchDelete();
        }
    };

    const kindLabel = (value) => t(`glossary_kind_${value}`, {
        defaultValue: value === 'main'
            ? 'Main glossary'
            : value === 'project'
                ? 'Project glossary'
                : 'Standard glossary',
    });
    const editableProjectOptions = useMemo(() => {
        if (!editTarget) return [];
        return projects
            .filter((project) => project.game_id === editTarget.game_id)
            .map((project) => ({
                value: project.project_id,
                label: project.status && project.status !== 'active'
                    ? `${project.name} (${project.status})`
                    : project.name,
            }))
            .sort((left, right) => left.label.localeCompare(right.label));
    }, [editTarget, projects]);

    const stats = [
        { label: t('glossary_overview_games', 'Games'), value: summary.game_count || 0 },
        { label: t('glossary_overview_glossaries', 'Glossaries'), value: summary.glossary_count || 0 },
        { label: t('glossary_overview_terms', 'Terms'), value: summary.term_count || 0 },
        { label: t('glossary_overview_bound_projects', 'Bound projects'), value: summary.bound_project_count || 0 },
    ];

    return (
        <div className={styles.overview} data-testid="glossary-overview">
            <Stack className={styles.overviewHeader} gap="lg">
                <div>
                <Group gap="xs" align="center">
                    <IconBook2 size={24} aria-hidden="true" />
                    <Title order={3}>{t('glossary_overview_title', 'Glossary overview')}</Title>
                    <Badge
                        variant="light"
                        color="blue"
                        leftSection={<IconInfoCircle size={13} aria-hidden="true" />}
                    >
                        {t(
                            'glossary_overview_global_scope',
                            'All games · All languages'
                        )}
                    </Badge>
                </Group>
                <Text c="dimmed" mt={6}>
                    {t('glossary_overview_summary', {
                        gameCount: summary.game_count || 0,
                        glossaryCount: summary.glossary_count || 0,
                        termCount: summary.term_count || 0,
                        defaultValue: 'Remis has {{glossaryCount}} glossaries from {{gameCount}} games, containing {{termCount}} terms.',
                    })}
                </Text>
                </div>

            <SimpleGrid cols={{ base: 2, xs: 4 }} spacing="sm">
                {stats.map((stat) => (
                    <Paper key={stat.label} p="md" className={styles.statCard} withBorder>
                        <Text size="xs" c="dimmed" fw={600}>{stat.label}</Text>
                        <Text size="xl" fw={800} className={styles.statValue}>{stat.value}</Text>
                    </Paper>
                ))}
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="md" align="end">
                <Stack gap={4}>
                    <TextInput
                        label={t('glossary_overview_search_label', 'Find a glossary')}
                        placeholder={t('glossary_overview_search_placeholder', 'Search by glossary, game, or project')}
                        leftSection={<IconSearch size={16} aria-hidden="true" />}
                        value={query}
                        onChange={(event) => setQuery(event.currentTarget.value)}
                    />
                    <Text
                        size="xs"
                        c="dimmed"
                        aria-live="polite"
                        data-testid="glossary-result-count"
                        data-visible={filteredGlossaries.length}
                        data-total={overview?.glossaries?.length || 0}
                    >
                        {t('glossary_overview_result_count', {
                            visible: filteredGlossaries.length,
                            total: overview?.glossaries?.length || 0,
                            defaultValue: '{{visible}} / {{total}} glossaries',
                        })}
                    </Text>
                </Stack>
                <Select
                    label={t('glossary_overview_type_filter', 'Glossary type')}
                    value={kind}
                    onChange={(value) => setKind(value || 'all')}
                    allowDeselect={false}
                    data={[
                        { value: 'all', label: t('glossary_kind_all', 'All types') },
                        { value: 'main', label: kindLabel('main') },
                        { value: 'project', label: kindLabel('project') },
                        { value: 'standard', label: kindLabel('standard') },
                    ]}
                />
            </SimpleGrid>

            <Paper className={styles.bulkToolbar} p="sm" withBorder data-testid="glossary-bulk-toolbar">
                <Group justify="space-between" wrap="wrap">
                    <Text size="sm" fw={700} c={selectedIds.length ? undefined : 'dimmed'}>
                        {selectedIds.length > 0
                            ? t('glossary_bulk_selected', {
                                count: selectedIds.length,
                                defaultValue: '{{count}} selected',
                            })
                            : t(
                                'glossary_bulk_none_selected',
                                'Select glossaries to use asset operations.'
                            )}
                    </Text>
                    <Group gap="xs" wrap="wrap">
                        <Button
                            size="xs"
                            variant="light"
                            leftSection={<IconCopy size={15} aria-hidden="true" />}
                            disabled={!singleSelectedGlossary}
                            onClick={() => openDuplicateDialog(singleSelectedGlossary)}
                        >
                            {t('glossary_duplicate_action', 'Duplicate glossary')}
                        </Button>
                        <GlossaryOperations
                            selectedIds={selectedIds}
                            glossaries={overview?.glossaries || []}
                            targetLanguages={targetLanguages}
                            apiProviders={apiProviders}
                            operation={operation}
                            isMutating={isMutating}
                            onPreviewMerge={onPreviewMerge}
                            onStartMerge={onStartMerge}
                            onStartHealthCheck={onStartHealthCheck}
                            onLoadHealthHistory={onLoadHealthHistory}
                        />
                        <Button
                            size="xs"
                            color="red"
                            variant="light"
                            leftSection={<IconTrash size={15} aria-hidden="true" />}
                            onClick={openBatchDeletePreview}
                            loading={isMutating}
                            disabled={selectedIds.length < 1}
                        >
                            {t('glossary_bulk_delete', 'Delete selected')}
                        </Button>
                    </Group>
                </Group>
            </Paper>
            </Stack>

            <Paper className={styles.inventoryCard} withBorder data-testid="glossary-inventory-panel">
                <ScrollArea
                    className={styles.inventoryScroll}
                    type="auto"
                    scrollbars="xy"
                    offsetScrollbars
                    data-testid="glossary-inventory-scroll"
                >
                    <Table
                        className={styles.inventoryTable}
                        striped
                        highlightOnHover
                        stickyHeader
                        verticalSpacing="sm"
                        miw={0}
                    >
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th className={styles.selectionCell}>
                                    <Checkbox
                                        aria-label={t('glossary_select_all_visible', 'Select all visible glossaries')}
                                        checked={allVisibleSelected}
                                        indeterminate={someVisibleSelected && !allVisibleSelected}
                                        onChange={(event) => toggleAllVisible(event.currentTarget.checked)}
                                    />
                                </Table.Th>
                                <Table.Th className={styles.nameCell}>{t('glossary_overview_name', 'Glossary')}</Table.Th>
                                <Table.Th className={styles.gameCell}>{t('glossary_game', 'Game')}</Table.Th>
                                <Table.Th className={styles.typeCell}>{t('glossary_overview_type', 'Type')}</Table.Th>
                                <Table.Th className={styles.termCell}>{t('glossary_overview_term_count', 'Terms')}</Table.Th>
                                <Table.Th className={styles.projectCell}>{t('glossary_overview_projects', 'Bound projects')}</Table.Th>
                                <Table.Th className={styles.updatedCell}>{t('glossary_overview_updated', 'Last updated')}</Table.Th>
                                <Table.Th className={styles.actionCell}>{t('glossary_actions', 'Actions')}</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {filteredGlossaries.map((glossary) => {
                                const projects = glossary.bound_projects || [];
                                return (
                                    <Table.Tr key={glossary.glossary_id}>
                                        <Table.Td className={styles.selectionCell}>
                                            <Checkbox
                                                aria-label={t('glossary_select_one', {
                                                    name: glossary.name,
                                                    defaultValue: 'Select {{name}}',
                                                })}
                                                checked={selectedIds.includes(glossary.glossary_id)}
                                                onChange={(event) => toggleGlossary(
                                                    glossary.glossary_id,
                                                    event.currentTarget.checked
                                                )}
                                            />
                                        </Table.Td>
                                        <Table.Td className={styles.nameCell}>
                                            <Text fw={700}>{glossary.name}</Text>
                                            {glossary.description && (
                                                <Text size="xs" c="dimmed" lineClamp={1}>{glossary.description}</Text>
                                            )}
                                        </Table.Td>
                                        <Table.Td className={styles.gameCell}><Text size="sm">{glossary.game_id}</Text></Table.Td>
                                        <Table.Td className={styles.typeCell}>
                                            <Badge
                                                className={styles.typeBadge}
                                                color={KIND_COLORS[glossary.kind] || 'gray'}
                                                variant="light"
                                            >
                                                {kindLabel(glossary.kind)}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td className={styles.termCell}><Text fw={700}>{glossary.entry_count || 0}</Text></Table.Td>
                                        <Table.Td className={styles.projectCell}>
                                            {projects.length > 0 ? (
                                                <Stack gap={2}>
                                                    {projects.slice(0, 2).map((project) => (
                                                        <Text key={project.project_id} size="sm">{project.name}</Text>
                                                    ))}
                                                    {projects.length > 2 && (
                                                        <Text size="xs" c="dimmed">
                                                            {t('glossary_overview_more_projects', {
                                                                count: projects.length - 2,
                                                                defaultValue: '+{{count}} more',
                                                            })}
                                                        </Text>
                                                    )}
                                                </Stack>
                                            ) : (
                                                <Text size="sm" c="dimmed">{t('glossary_overview_unbound', 'Not bound')}</Text>
                                            )}
                                        </Table.Td>
                                        <Table.Td className={styles.updatedCell}>
                                            <Text size="sm">
                                                {formatUpdatedAt(
                                                    glossary.updated_at,
                                                    t('glossary_overview_unknown_date', 'Unknown'),
                                                    getResolvedInterfaceLocale(i18n),
                                                )}
                                            </Text>
                                        </Table.Td>
                                        <Table.Td className={styles.actionCell}>
                                            <GlossaryRowActions
                                                glossary={glossary}
                                                onOpen={onOpenGlossary}
                                                onEdit={openEditDialog}
                                                className={styles.actionGroup}
                                            />
                                        </Table.Td>
                                    </Table.Tr>
                                );
                            })}
                            {!isLoading && filteredGlossaries.length === 0 && (
                                <Table.Tr>
                                    <Table.Td colSpan={8}>
                                        <Text ta="center" c="dimmed" py="xl">
                                            {t('glossary_overview_empty', 'No glossaries match these filters.')}
                                        </Text>
                                    </Table.Td>
                                </Table.Tr>
                            )}
                        </Table.Tbody>
                    </Table>
                </ScrollArea>
            </Paper>

            <Modal
                opened={Boolean(duplicateTarget)}
                onClose={closeDuplicateDialog}
                title={t('glossary_duplicate_title', 'Create glossary copy')}
                centered
            >
                <Stack>
                    <Text size="sm">
                        {t('glossary_duplicate_summary', {
                            name: duplicateTarget?.name || '',
                            count: duplicateTarget?.entry_count || 0,
                            defaultValue: 'Copy {{count}} entries from {{name}} into a new independent glossary.',
                        })}
                    </Text>
                    <Text size="sm" c="dimmed">
                        {t(
                            'glossary_duplicate_binding_note',
                            'Project bindings and main-glossary status are not copied.'
                        )}
                    </Text>
                    <TextInput
                        label={t('glossary_duplicate_name_label', 'Copy name')}
                        value={duplicateName}
                        error={duplicateNameError}
                        onChange={(event) => {
                            setDuplicateName(event.currentTarget.value);
                            setDuplicateNameError('');
                        }}
                        maxLength={200}
                        required
                        autoFocus
                    />
                    <Group justify="flex-end">
                        <Button variant="default" onClick={closeDuplicateDialog} disabled={isMutating}>
                            {t('cancel', 'Cancel')}
                        </Button>
                        <Button onClick={confirmDuplicate} loading={isMutating}>
                            {t('glossary_duplicate_confirm', 'Create copy')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={Boolean(editTarget)}
                onClose={closeEditDialog}
                title={t('glossary_edit_metadata_title', 'Edit glossary information')}
                centered
                scrollAreaComponent={ScrollArea.Autosize}
            >
                <Stack>
                    <TextInput
                        label={t('glossary_edit_metadata_name', 'Glossary name')}
                        value={editName}
                        error={editNameError}
                        onChange={(event) => {
                            setEditName(event.currentTarget.value);
                            setEditNameError('');
                        }}
                        maxLength={200}
                        required
                        autoFocus
                    />
                    <Textarea
                        label={t('glossary_edit_metadata_description', 'Description')}
                        value={editDescription}
                        onChange={(event) => setEditDescription(event.currentTarget.value)}
                        maxLength={2000}
                        minRows={3}
                        autosize
                    />
                    <Select
                        label={t('glossary_edit_metadata_kind', 'Glossary type')}
                        value={editKind}
                        allowDeselect={false}
                        data={[
                            { value: 'main', label: kindLabel('main') },
                            { value: 'project', label: kindLabel('project') },
                            { value: 'standard', label: kindLabel('standard') },
                        ]}
                        onChange={(value) => {
                            const nextKind = value || 'standard';
                            setEditKind(nextKind);
                            setEditProjectError('');
                            if (nextKind !== 'project') setEditProjectIds([]);
                        }}
                    />
                    <MultiSelect
                        label={t('glossary_edit_metadata_projects', 'Bound projects')}
                        description={t(
                            'glossary_edit_metadata_projects_desc',
                            'A glossary and a project may each participate in multiple bindings.'
                        )}
                        placeholder={t(
                            'glossary_edit_metadata_projects_placeholder',
                            'Search projects from this game'
                        )}
                        value={editProjectIds}
                        data={editableProjectOptions}
                        searchable
                        clearable
                        error={editProjectError}
                        nothingFoundMessage={t(
                            'glossary_edit_metadata_projects_empty',
                            'No projects are available for this game.'
                        )}
                        onChange={(values) => {
                            setEditProjectIds(values);
                            setEditProjectError('');
                            setEditKind(values.length > 0 ? 'project' : 'standard');
                        }}
                    />
                    <Text size="xs" c="dimmed">
                        {t(
                            'glossary_edit_metadata_scope',
                            'Binding one or more projects makes this project-specific. Clearing every binding makes it standard. Each game can have only one main glossary.'
                        )}
                    </Text>
                    <Group justify="flex-end">
                        <Button variant="default" onClick={closeEditDialog} disabled={isMutating}>
                            {t('cancel', 'Cancel')}
                        </Button>
                        <Button onClick={confirmEdit} loading={isMutating}>
                            {t('glossary_edit_metadata_save', 'Save information')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={Boolean(deleteImpact)}
                onClose={closeBatchDelete}
                title={t('glossary_bulk_delete_title', 'Review deletion impact')}
                size="lg"
                centered
            >
                {deleteImpact && (
                    <Stack>
                        <Alert
                            color="red"
                            icon={<IconAlertTriangle size={18} aria-hidden="true" />}
                            title={t('glossary_bulk_delete_warning_title', 'Permanent deletion')}
                        >
                            {t('glossary_bulk_delete_summary', {
                                glossaryCount: deleteImpact.glossary_count,
                                termCount: deleteImpact.term_count,
                                defaultValue: 'This will permanently delete {{glossaryCount}} glossaries and {{termCount}} terms.',
                            })}
                        </Alert>

                        <Stack gap={4} className={styles.impactList}>
                            {deleteImpact.glossaries.map((glossary) => (
                                <Group key={glossary.glossary_id} justify="space-between" wrap="nowrap">
                                    <Text size="sm" fw={600}>{glossary.name}</Text>
                                    <Text size="xs" c="dimmed">
                                        {glossary.entry_count} {t('glossary_overview_terms', 'terms')}
                                    </Text>
                                </Group>
                            ))}
                        </Stack>

                        {deleteImpact.main_glossaries.length > 0 && (
                            <Checkbox
                                checked={confirmMainGlossaries}
                                onChange={(event) => setConfirmMainGlossaries(event.currentTarget.checked)}
                                label={t('glossary_bulk_confirm_main', {
                                    count: deleteImpact.main_glossaries.length,
                                    defaultValue: 'I understand that {{count}} main glossaries will be deleted.',
                                })}
                            />
                        )}

                        {deleteImpact.bound_projects.length > 0 && (
                            <Checkbox
                                checked={confirmProjectBindings}
                                onChange={(event) => setConfirmProjectBindings(event.currentTarget.checked)}
                                label={t('glossary_bulk_confirm_bindings', {
                                    count: deleteImpact.bound_projects.length,
                                    defaultValue: 'I understand that {{count}} project bindings will be removed and terminology consistency may be affected.',
                                })}
                            />
                        )}

                        <Group justify="flex-end">
                            <Button variant="default" onClick={closeBatchDelete} disabled={isMutating}>
                                {t('cancel', 'Cancel')}
                            </Button>
                            <Button
                                color="red"
                                onClick={confirmBatchDelete}
                                loading={isMutating}
                                disabled={
                                    (deleteImpact.main_glossaries.length > 0 && !confirmMainGlossaries)
                                    || (deleteImpact.bound_projects.length > 0 && !confirmProjectBindings)
                                }
                            >
                                {t('glossary_bulk_delete_confirm', 'Delete permanently')}
                            </Button>
                        </Group>
                    </Stack>
                )}
            </Modal>
        </div>
    );
};

export default GlossaryOverview;
