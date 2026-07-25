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

  it('uses the canvas contrast contract for the transparent action description', () => {
    renderView();

    const description = screen.getByText('从本地 Mod 文件夹开始新的翻译。');
    expect(description.closest('[data-remis-surface]')).toHaveAttribute(
      'data-remis-surface',
      'canvas',
    );
  });

  it('uses distinct semantic colors for different game tags', () => {
    renderView({
      projects: [
        { project_id: 'hoi4', name: 'HOI4 project', game_id: 'hoi4', status: 'active' },
        { project_id: 'eu5', name: 'EU5 project', game_id: 'eu5', status: 'active' },
        { project_id: 'stellaris', name: 'Stellaris project', game_id: 'stellaris', status: 'active' },
      ],
    });

    expect(screen.getByText('hoi4').closest('[data-game-color]')).toHaveAttribute('data-game-color', 'olive');
    expect(screen.getByText('eu5').closest('[data-game-color]')).toHaveAttribute('data-game-color', 'orange');
    expect(screen.getByText('stellaris').closest('[data-game-color]')).toHaveAttribute('data-game-color', 'grape');
  });
});
