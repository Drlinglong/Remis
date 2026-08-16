import React from 'react';
import { DndContext, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { Badge, Box, Group, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { MemoryRouter } from 'react-router';

import { SidebarProvider } from '../context/SidebarContext';
import { KanbanColumn } from '../components/tools/KanbanColumn';
import { ProjectDashboardView } from '../components/projectManagement/ProjectDashboardView';
import { ProjectListView } from '../components/projectManagement/ProjectListView';
import kanbanStyles from '../components/tools/KanbanBoard.module.css';
import styles from './ProjectManagementVisualFixture.module.css';

const translations = {
    button_back: '返回项目列表',
    page_title_project_management: '项目管理',
    'project_management.hero_desc': '管理本地化项目、文件与工作状态。',
    'project_management.archives_title': '项目档案',
    'project_management.actions.archives_desc': '查看已归档的项目。',
    'project_management.file_list.table.actions': '项目操作',
    'project_management.actions.create_new': '创建新项目',
    'project_management.actions.create_new_desc': '从本地 Mod 文件夹开始新的翻译。',
    'project_management.actions.archives': '打开档案',
    'project_management.workspace_label': '项目档案馆',
    'project_management.active_projects': '活动项目',
    'project_management.project_count': '1 个项目',
    'project_management.current_project': '当前项目',
    'project_management.source_language': '源语言',
    'project_management.workspace_navigation': '项目工作区导航',
    'project_management.main_flow': '主流程',
    'project_management.project_tools': '项目工具',
    'translation_page.search_placeholder': '搜索项目…',
    'project_management.tabs_overview': '总览',
    'project_management.tabs_validation': '验证',
    'project_management.tabs_history': '历史',
    'project_management.more_views': '更多视图',
    'project_management.tabs_project_glossary': '项目词典',
    'project_management.tabs_kanban': '任务看板',
    'project_management.tabs_publishing_assets': '发布素材',
    'project_management.status.active': '进行中',
    'project_management.kanban.columns.todo': '待处理',
    'project_management.kanban.columns.in_progress': '进行中',
    'project_management.kanban.columns.proofreading': '校对中',
    'project_management.kanban.columns.paused': '已暂停',
    'project_management.kanban.columns.done': '已完成',
    'project_management.kanban.badge_source': '源文件',
    'project_management.kanban.badge_translation': '译文',
    'project_management.kanban.badge_metadata': '元数据',
    'project_management.details.lines_count': '行数：{{count}}',
    'project_management.file_list_title': '文件列表（{{count}}）',
    'project_management.file_type.source': '源文件',
    'project_management.file_type.translation': '译文',
    proofreading: '校对',
};

const fixtureT = (key, fallback) => translations[key] || (typeof fallback === 'string' ? fallback : key);

const selectedProject = {
    project_id: 'project-management-fixture',
    name: 'Expedition Demo — Project Management',
    game_id: 'vic3',
    status: 'active',
    source_language: 'English',
    last_updated: '2026-08-01T12:00:00Z',
};

const projectDetails = {
    ...selectedProject,
    source_path: String.raw`C:\Mods\Expedition\localisation`,
    translation_dirs: [String.raw`C:\Mods\Expedition\localisation\simp_chinese`],
    archived_languages: ['简体中文'],
    has_available_translation: false,
    validation: { issues_count: 0 },
    overview: {
        translated: 64,
        toBeProofread: 12,
        totalFiles: 8,
        totalLines: 1842,
    },
    files: [
        {
            key: 'events-source',
            name: String.raw`C:\Mods\Expedition\localisation\events_l_english.yml`,
            file_type: 'source',
            lines: 240,
            status: 'done',
            progress: '100%',
            actions: [],
        },
        {
            key: 'events-translation',
            name: String.raw`C:\Mods\Expedition\localisation\simp_chinese\events_l_simp_chinese.yml`,
            file_type: 'translation',
            lines: 226,
            status: 'proofreading',
            progress: '78%',
            actions: ['Proofread'],
        },
    ],
};

const kanbanTasks = [
    {
        id: 'fixture-source-task',
        type: 'file',
        title: 'events_l_english.yml',
        status: 'todo',
        meta: { file_type: 'source', source_lines: 240 },
    },
    {
        id: 'fixture-proofread-task',
        type: 'file',
        title: 'events_l_simp_chinese.yml',
        status: 'proofreading',
        meta: { file_type: 'translation', lines: 226 },
        comments: '等待人工校对确认。',
    },
    {
        id: 'fixture-done-task',
        type: 'note',
        title: 'Metadata review completed',
        status: 'done',
        comments: 'Deterministic visual fixture task.',
    },
];

const noop = () => undefined;

const normalizeFixtureLanguage = (language = 'en') => {
    if (language.toLowerCase().startsWith('zh')) return 'zh';
    if (language.toLowerCase() === 'pt-br') return 'pt-BR';
    return language.split('-')[0];
};

function FixtureFrame({ children, localeReady, scenario, themeId }) {
    return (
        <Box
            className={styles.page}
            data-remis-surface="canvas"
            data-testid={`project-management-${scenario}`}
            data-theme-id={themeId}
            data-visual-ready={localeReady ? 'true' : 'loading'}
        >
            <Box className={styles.scenario}>
                <Group className={styles.scenarioHeading} justify="space-between" align="flex-start">
                    <Box>
                        <Text size="xs" tt="uppercase">ProjectManagement CSS ownership fixture</Text>
                        <Title order={2}>{scenario}</Title>
                    </Box>
                    <Badge variant="outline">{themeId}</Badge>
                </Group>
                {children}
            </Box>
        </Box>
    );
}

function ActiveListFixture() {
    return (
        <ProjectListView
            projects={[selectedProject]}
            searchQuery=""
            setIsCreateModalOpen={noop}
            setSearchQuery={noop}
            setSelectedProjectId={noop}
            setViewMode={noop}
            t={fixtureT}
            viewMode="active"
        />
    );
}

function DashboardDetailFixture() {
    return (
        <MemoryRouter>
            <SidebarProvider>
                <ProjectDashboardView
                    activeTab="overview"
                    fetchProjectFiles={noop}
                    fetchProjects={noop}
                    handleFileStatusChange={noop}
                    handleOpenManage={noop}
                    handleProofread={noop}
                    handleRefreshFiles={noop}
                    handleRepairMetadata={noop}
                    handleUpdateNotes={noop}
                    handleUpdateStatus={noop}
                    metadataRepairLoading={false}
                    projectDataRefreshToken={0}
                    projectDetails={projectDetails}
                    selectedProject={selectedProject}
                    setActiveTab={noop}
                    setDeleteModalOpen={noop}
                    setProjectDataRefreshToken={noop}
                    setSelectedProjectId={noop}
                    t={fixtureT}
                />
            </SidebarProvider>
        </MemoryRouter>
    );
}

function KanbanFixture() {
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 1 } }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
            keyboardCodes: { start: ['Space'], cancel: ['Escape'], end: ['Space'] },
        }),
    );
    const columns = ['todo', 'in_progress', 'proofreading', 'paused', 'done'];

    return (
        <SidebarProvider>
            <Box className={styles.kanbanFrame} data-testid="project-management-kanban-board">
                <DndContext sensors={sensors} onDragEnd={noop}>
                    <div id="kanban-board" className={kanbanStyles.boardContainer}>
                        {columns.map((column) => (
                            <KanbanColumn
                                key={column}
                                id={column}
                                tasks={kanbanTasks.filter((task) => task.status === column)}
                                onCardClick={noop}
                                onAddNote={noop}
                            />
                        ))}
                    </div>
                </DndContext>
            </Box>
        </SidebarProvider>
    );
}

export default function ProjectManagementVisualFixture({ scenario = 'active-list', themeId }) {
    const { i18n } = useTranslation();
    const activeLanguage = i18n.resolvedLanguage || i18n.language || 'en';
    const expectedLanguage = normalizeFixtureLanguage(
        typeof navigator === 'undefined' ? activeLanguage : navigator.language,
    );
    const resolvedLanguage = normalizeFixtureLanguage(activeLanguage);
    const localeReady = resolvedLanguage === expectedLanguage
        && (i18n.hasResourceBundle(activeLanguage, 'translation')
            || i18n.hasResourceBundle(resolvedLanguage, 'translation'));
    const content = scenario === 'active-list'
        ? <ActiveListFixture />
        : scenario === 'dashboard-detail'
            ? <DashboardDetailFixture />
            : <KanbanFixture />;

    return (
        <FixtureFrame localeReady={localeReady} scenario={scenario} themeId={themeId}>
            {content}
        </FixtureFrame>
    );
}
