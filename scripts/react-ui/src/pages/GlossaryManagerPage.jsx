import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
    Select, Input, Title, Button, Group, LoadingOverlay,
    Tooltip, Text, Paper, ScrollArea, Table, ActionIcon, Stack,
    Modal
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconTrash, IconDots, IconTrashX } from '@tabler/icons-react';
import {
    useReactTable,
    getCoreRowModel,
    flexRender,
    getFilteredRowModel,
} from '@tanstack/react-table';
import { useSidebar } from '../context/SidebarContext';
import { useTutorial } from '../context/TutorialContext';
import useGlossaryActions from '../hooks/useGlossaryActions';
import FileTree from '../components/glossary/FileTree';
import NewFileModal from '../components/glossary/NewFileModal';
import EditTermForm from '../components/glossary/EditTermForm';
import styles from './GlossaryManager.module.css';

/**
 * 词典管理页面
 * 轻量级容器，仅负责布局和组件组合
 */
const GlossaryManagerPage = () => {
    const { t } = useTranslation();
    const { setSidebarWidth, setSidebarCollapsed } = useSidebar();
    const { setPageContext } = useTutorial();

    useEffect(() => {
        setPageContext('glossaryManager');
    }, [setPageContext]);

    // Hook 集中管理所有状态和逻辑
    const glossary = useGlossaryActions();

    // 本地 UI 状态
    const [selectedTerm, setSelectedTerm] = useState(null);
    const [isFileCreateModalVisible, setIsFileCreateModalVisible] = useState(false);
    const [isDeleteModalVisible, setIsDeleteModalVisible] = useState(false);
    const [deletingItemId, setDeletingItemId] = useState(null);
    const [isDeleteGlossaryModalVisible, setIsDeleteGlossaryModalVisible] = useState(false);

    // 行点击处理
    const handleRowClick = (entry) => {
        setSelectedTerm(entry);
        setSidebarWidth(450);
        setSidebarCollapsed(false);
    };

    // 关闭面板
    const handleClosePanel = () => {
        setSelectedTerm(null);
        setSidebarWidth(300);
    };

    // 删除词条确认
    const showDeleteModal = (id) => {
        setDeletingItemId(id);
        setIsDeleteModalVisible(true);
    };

    const handleDeleteConfirm = async () => {
        const success = await glossary.handleDelete(deletingItemId);
        if (success) {
            setIsDeleteModalVisible(false);
            setDeletingItemId(null);
            if (selectedTerm && selectedTerm.id === deletingItemId) {
                setSelectedTerm(null);
            }
        }
    };

    // 删除整本词典确认
    const handleDeleteGlossaryConfirm = async () => {
        const success = await glossary.handleDeleteGlossary();
        if (success) {
            setIsDeleteGlossaryModalVisible(false);
            setSelectedTerm(null);
        }
    };

    // 表格列定义
    const columns = [
        {
            accessorKey: 'source',
            header: () => <Text fw={700}>{t('glossary_source_text')}</Text>,
            cell: info => <Text>{info.getValue()}</Text>
        },
        {
            id: 'translation',
            header: () => <Text fw={700}>{t('glossary_translation')}</Text>,
            cell: ({ row }) => <Text>{row.original.translations[glossary.selectedTargetLang] || ''}</Text>
        },
        {
            accessorKey: 'notes',
            header: () => <Text fw={700}>{t('glossary_notes')}</Text>,
            cell: ({ row }) => (
                row.original.notes ? (
                    <Tooltip label={t('glossary_view_edit_notes')}>
                        <IconDots size={14} />
                    </Tooltip>
                ) : null
            )
        },
        {
            id: 'actions',
            header: () => <Text fw={700}>{t('glossary_actions')}</Text>,
            cell: ({ row }) => (
                <Group gap="xs" onClick={(e) => e.stopPropagation()}>
                    <ActionIcon color="red" onClick={() => showDeleteModal(row.original.id)}>
                        <IconTrash size={14} />
                    </ActionIcon>
                </Group>
            )
        },
    ];

    const table = useReactTable({
        data: glossary.data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        manualPagination: true,
        manualFiltering: true,
        pageCount: Math.ceil(glossary.rowCount / glossary.pagination.pageSize),
        state: {
            globalFilter: glossary.filtering,
            pagination: glossary.pagination
        },
        onPaginationChange: glossary.setPagination,
        onGlobalFilterChange: glossary.setFiltering,
    });

    return (
        <div className={styles.pageContainer}>
            <LoadingOverlay visible={glossary.isSaving} />

            <div className={styles.columnsWrapper}>
                {/* Left Panel: File Tree */}
                <div id="glossary-file-list" className={styles.leftPanel}>
                    <Paper p="md" className={styles.sidebarCard}>
                        <LoadingOverlay visible={glossary.isLoadingTree} />
                        <Title order={4}>{t('glossary_manager_title')}</Title>

                        <Stack gap="sm" mb="md" mt="md">
                            <Select
                                label={t('glossary_game')}
                                data={glossary.treeData.map(g => ({ value: g.key, label: g.title || g.key }))}
                                value={glossary.selectedGame}
                                onChange={glossary.setSelectedGame}
                            />
                            <Select
                                label={t('glossary_target_language')}
                                data={glossary.targetLanguages.map(l => ({ value: l.code, label: l.name_local || l.code }))}
                                value={glossary.selectedTargetLang}
                                onChange={glossary.setSelectedTargetLang}
                            />
                        </Stack>

                        <Group justify="space-between" mb="xs">
                            <Text size="sm" fw={500}>{t('glossary_files')}</Text>
                            <Tooltip label={t('glossary_create_new_file')}>
                                <Button
                                    size="xs"
                                    variant="light"
                                    onClick={() => setIsFileCreateModalVisible(true)}
                                    disabled={!glossary.selectedGame}
                                >
                                    <IconPlus size={14} />
                                </Button>
                            </Tooltip>
                        </Group>

                        <ScrollArea style={{ flex: 1, minHeight: 0 }}>
                            {glossary.selectedGame && (
                                <FileTree
                                    nodes={glossary.treeData.find(n => n.key === glossary.selectedGame)?.children || []}
                                    onSelect={glossary.onSelectTree}
                                    selectedKey={glossary.selectedFile.key}
                                />
                            )}
                        </ScrollArea>
                    </Paper>
                </div>

                {/* Main Panel: Table */}
                <div className={styles.mainPanel}>
                    <Paper p="md" className={styles.contentCard}>
                        <LoadingOverlay visible={glossary.isLoadingContent} />

                        <Group justify="space-between" mb="md">
                            <Title order={4}>
                                {glossary.selectedFile.key
                                    ? glossary.selectedFile.title
                                    : t('glossary_select_file_prompt')}
                            </Title>
                            <Group gap="xs">
                                <Button
                                    leftSection={<IconPlus size={16} />}
                                    onClick={() => handleRowClick({})}
                                    disabled={!glossary.selectedFile.key}
                                >
                                    {t('glossary_add_entry')}
                                </Button>
                                <Tooltip label={t('glossary_delete_glossary_tooltip')}>
                                    <Button
                                        color="red"
                                        variant="outline"
                                        leftSection={<IconTrashX size={16} />}
                                        onClick={() => setIsDeleteGlossaryModalVisible(true)}
                                        disabled={!glossary.selectedFile.key}
                                    >
                                        {t('glossary_delete_glossary')}
                                    </Button>
                                </Tooltip>
                            </Group>
                        </Group>

                        <Group mb="md" gap="xs">
                            <Input
                                id="glossary-search"
                                placeholder={t('glossary_filter_placeholder')}
                                value={glossary.filtering}
                                onChange={e => {
                                    glossary.setFiltering(e.currentTarget.value);
                                    glossary.setPagination(p => ({ ...p, pageIndex: 0 }));
                                }}
                                style={{ flex: 1 }}
                            />
                            <Select
                                value={glossary.searchScope}
                                onChange={(val) => {
                                    glossary.setSearchScope(val);
                                    glossary.setPagination(p => ({ ...p, pageIndex: 0 }));
                                }}
                                data={[
                                    { value: 'file', label: t('search_scope_file') },
                                    { value: 'game', label: t('search_scope_game') },
                                    { value: 'all', label: t('search_scope_all') }
                                ]}
                                style={{ width: 160 }}
                                allowDeselect={false}
                            />
                        </Group>

                        <ScrollArea style={{ flex: 1, minHeight: 0 }}>
                            <Table id="glossary-entries-table" striped highlightOnHover withTableBorder>
                                <Table.Thead>
                                    {table.getHeaderGroups().map(hg => (
                                        <Table.Tr key={hg.id}>
                                            {hg.headers.map(header => (
                                                <Table.Th key={header.id}>
                                                    {flexRender(header.column.columnDef.header, header.getContext())}
                                                </Table.Th>
                                            ))}
                                        </Table.Tr>
                                    ))}
                                </Table.Thead>
                                <Table.Tbody>
                                    {table.getRowModel().rows.length > 0 ? (
                                        table.getRowModel().rows.map(row => (
                                            <Table.Tr
                                                key={row.id}
                                                onClick={() => handleRowClick(row.original)}
                                                className={selectedTerm && selectedTerm.id === row.original.id ? styles.selectedRow : ''}
                                            >
                                                {row.getVisibleCells().map(cell => (
                                                    <Table.Td key={cell.id}>
                                                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                                    </Table.Td>
                                                ))}
                                            </Table.Tr>
                                        ))
                                    ) : (
                                        <Table.Tr>
                                            <Table.Td colSpan={columns.length} style={{ textAlign: 'center', padding: '20px' }}>
                                                <Text c="dimmed">{t('glossary_no_entries')}</Text>
                                            </Table.Td>
                                        </Table.Tr>
                                    )}
                                </Table.Tbody>
                            </Table>
                        </ScrollArea>

                        <Group justify="space-between" mt="md">
                            <Group>
                                <Select
                                    style={{ width: 120 }}
                                    value={String(table.getState().pagination.pageSize)}
                                    onChange={value => table.setPageSize(Number(value))}
                                    data={['25', '50', '100'].map(size => ({
                                        value: size,
                                        label: t('glossary_show_entries', { count: size })
                                    }))}
                                />
                                <Text size="sm" c="dimmed">
                                    {t('glossary_page_info', {
                                        page: table.getState().pagination.pageIndex + 1,
                                        total: table.getPageCount()
                                    })}
                                </Text>
                            </Group>
                            <Button.Group>
                                <Button
                                    variant="default"
                                    onClick={() => table.previousPage()}
                                    disabled={!table.getCanPreviousPage()}
                                >
                                    {t('glossary_previous_page')}
                                </Button>
                                <Button
                                    variant="default"
                                    onClick={() => table.nextPage()}
                                    disabled={!table.getCanNextPage()}
                                >
                                    {t('glossary_next_page')}
                                </Button>
                            </Button.Group>
                        </Group>
                    </Paper>
                </div>
            </div>

            {/* New File Modal */}
            <NewFileModal
                opened={isFileCreateModalVisible}
                onClose={() => setIsFileCreateModalVisible(false)}
                onSubmit={glossary.handleCreateFile}
                isLoading={glossary.isSaving}
            />

            {/* Edit Term Form (Portal) */}
            <EditTermForm
                selectedTerm={selectedTerm}
                onClose={handleClosePanel}
                onSave={glossary.handleSave}
                targetLanguages={glossary.targetLanguages}
                selectedTargetLang={glossary.selectedTargetLang}
                isSaving={glossary.isSaving}
            />

            {/* Delete Glossary Confirmation Modal */}
            <Modal
                opened={isDeleteGlossaryModalVisible}
                onClose={() => setIsDeleteGlossaryModalVisible(false)}
                title={t('glossary_delete_glossary_confirm_title')}
                centered
            >
                <Text mb="lg">
                    {t('glossary_delete_glossary_confirm_message', { name: glossary.selectedFile.title })}
                </Text>
                <Group justify="flex-end">
                    <Button variant="default" onClick={() => setIsDeleteGlossaryModalVisible(false)}>
                        {t('cancel')}
                    </Button>
                    <Button color="red" onClick={handleDeleteGlossaryConfirm} loading={glossary.isSaving}>
                        {t('btn_confirm_reset')}
                    </Button>
                </Group>
            </Modal>
        </div>
    );
};

export default GlossaryManagerPage;
