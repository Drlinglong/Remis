import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { ProjectListView } from './ProjectListView';

const translations = {
  'page_title_project_management': '项目管理',
  'project_management.hero_desc': '管理本地化项目',
  'project_management.file_list.table.actions': '操作',
  'project_management.actions.create_new': '创建新项目',
  'project_management.actions.create_new_desc': '从本地 Mod 文件夹开始新的翻译。',
  'project_management.actions.archives': '档案馆',
  'translation_page.search_placeholder': '搜索项目...',
};

function renderView(overrides = {}) {
  const props = {
    projects: [],
    searchQuery: '',
    setIsCreateModalOpen: vi.fn(),
    setSearchQuery: vi.fn(),
    setSelectedProjectId: vi.fn(),
    setViewMode: vi.fn(),
    t: (key) => translations[key] || key,
    viewMode: 'active',
    ...overrides,
  };

  return {
    ...render(
      <MantineProvider>
        <ProjectListView {...props} />
      </MantineProvider>,
    ),
    props,
  };
}

describe('ProjectListView', () => {
  it('presents one primary create action and a secondary archive action', () => {
    const { props } = renderView();

    fireEvent.click(screen.getByRole('button', { name: '创建新项目' }));
    fireEvent.click(screen.getByRole('button', { name: '档案馆' }));

    expect(props.setIsCreateModalOpen).toHaveBeenCalledWith(true);
    expect(props.setViewMode).toHaveBeenCalledWith('archives');
    expect(screen.getByPlaceholderText('搜索项目...')).toBeInTheDocument();
  });
});
