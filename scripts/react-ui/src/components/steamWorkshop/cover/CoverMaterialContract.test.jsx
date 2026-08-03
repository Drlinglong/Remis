import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';
import { CoverInspector } from './CoverInspector';
import { CoverToolbox } from './CoverToolbox';
import { expandPseudoLocale } from '../../../test/pseudoLocalization';

const toolboxSource = readFileSync(
    resolve(process.cwd(), 'src/components/steamWorkshop/cover/CoverToolbox.jsx'),
    'utf8',
);
const inspectorSource = readFileSync(
    resolve(process.cwd(), 'src/components/steamWorkshop/cover/CoverInspector.jsx'),
    'utf8',
);

const labels = {
    toolboxTitle: '工具箱',
    useProjectThumbnail: '使用项目封面图',
    useProjectThumbnailTooltip: '将尝试寻找该项目的原始封面图并作为背景使用',
    addFlags: '添加国旗',
    addText: '添加文本',
    addAllFlags: '一键添加所有旗帜',
    resetCanvas: '重置画布',
    deleteCanvas: '删除画布',
    inspectorTitle: '属性检查器',
    backgroundColor: '背景颜色',
    uploadBackground: '上传背景图片',
    elementProperties: '元素属性',
    textContent: '文本内容',
    fontSize: '字体大小',
    fontFamily: '字体',
    color: '颜色',
    deleteElement: '删除元素',
    uploadEmblem: '上传自定义标识',
};

const createEditor = () => ({
    addAllFlags: vi.fn(),
    addFileImage: vi.fn(),
    addFlag: vi.fn(),
    addText: vi.fn(),
    backgroundColor: '#ffffff',
    deleteSelected: vi.fn(),
    inputRefs: {
        backgroundInputRef: { current: null },
        emblemInputRef: { current: null },
        modImageInputRef: { current: null },
    },
    selectedElement: null,
    setBackgroundColor: vi.fn(),
    setBackgroundImage: vi.fn(),
    setElements: vi.fn(),
    setSelectedId: vi.fn(),
    resetCanvas: vi.fn(),
});

describe('cover editor material contract', () => {
    it('renders paper controls with readable labels and no toolbox heading', () => {
        const editor = createEditor();
        const { container } = render(
            <MantineProvider>
                <CoverToolbox
                    canLoadProjectThumbnail
                    editor={editor}
                    labels={labels}
                    onLoadProjectThumbnail={vi.fn()}
                />
                <CoverInspector editor={editor} labels={labels} />
            </MantineProvider>,
        );

        expect(container.querySelectorAll('[data-remis-surface="paper"]')).toHaveLength(2);
        expect(container.querySelectorAll('[data-remis-surface="surface"]')).toHaveLength(0);
        expect(screen.queryByRole('heading', { name: '工具箱' })).not.toBeInTheDocument();
        expect(screen.getByRole('heading', { name: '添加国旗' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: '属性检查器' })).toBeInTheDocument();
        expect(screen.getByText('背景颜色')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '使用项目封面图' })).toBeEnabled();
    });

    it('keeps a long Russian project-cover action in the overflow-aware button path', () => {
        const editor = createEditor();
        const russianLabel = expandPseudoLocale('Использовать обложку проекта');
        const { container } = render(
            <MantineProvider>
                <CoverToolbox
                    canLoadProjectThumbnail
                    editor={editor}
                    labels={{ ...labels, useProjectThumbnail: russianLabel }}
                    onLoadProjectThumbnail={vi.fn()}
                />
            </MantineProvider>,
        );

        const button = screen.getByRole('button', { name: russianLabel });
        expect(button).toHaveClass('cover-toolbox-project-thumbnail');
        expect(container.querySelector('.overflow-aware-label')).toHaveClass('overflow-aware-label');
        expect(button).toHaveAttribute('data-variant', 'light');
    });

    it('keeps the source bound to paper semantics instead of surface tokens', () => {
        [toolboxSource, inspectorSource].forEach((source) => {
            expect(source).toContain('data-remis-surface="paper"');
            expect(source).not.toContain('data-remis-surface="surface"');
        });
        expect(toolboxSource).not.toContain('labels.toolboxTitle');
        expect(toolboxSource).toContain('labels.addFlags');
        expect(toolboxSource).toContain('labels.useProjectThumbnailTooltip');
        expect(toolboxSource).not.toContain('modImageInputRef');
        expect(inspectorSource).toContain('labels.inspectorTitle');
        expect(inspectorSource).toContain('labels.backgroundColor');
    });
});
