import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
    Badge,
    Group,
    SegmentedControl,
    Text,
    TextInput,
    Textarea,
    Tooltip
} from '@mantine/core';
import {
    IconAlertTriangle,
    IconCode,
    IconHash,
    IconHelpCircle,
    IconSearch
} from '@tabler/icons-react';
import classes from './ProofreadingEntryWorkspace.module.css';
import { isProofreadingRowChanged } from './proofreadingEntryState';

const ColumnHeader = ({ label, description }) => (
    <Group gap={5} wrap="nowrap" className={classes.headerCell}>
        <Text fw={700} c="dimmed" inherit>{label}</Text>
        <Tooltip label={description} multiline w={260} withArrow>
            <IconHelpCircle
                size={15}
                className={classes.headerHelp}
                aria-label={description}
                tabIndex={0}
            />
        </Tooltip>
    </Group>
);

const ProofreadingEntryWorkspace = ({
    rows,
    loading,
    validationResults,
    onFinalValueChange,
    query,
    onQueryChange,
    filter,
    onFilterChange,
    focusEntryKey,
    initialScrollOffset,
    onScrollOffsetChange,
    onFocusedEntryChange,
}) => {
    const { t } = useTranslation();
    const [highlightedEntryKey, setHighlightedEntryKey] = useState(null);
    const scrollRef = useRef(null);
    const scrollFrameRef = useRef(null);
    const handledFocusRef = useRef(null);

    const issueKeys = useMemo(() => {
        const keys = new Set();
        validationResults.forEach(issue => {
            if (issue.key) keys.add(issue.key);
        });
        return keys;
    }, [validationResults]);

    const filteredRows = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return rows.filter(row => {
            const changed = isProofreadingRowChanged(row);
            if (filter === 'changed' && !changed) return false;
            if (filter === 'issues' && !issueKeys.has(row.key)) return false;

            if (!normalizedQuery) return true;
            const haystack = [
                row.key,
                row.source_value,
                row.ai_value,
                row.final_value,
                row.display_text,
            ].filter(Boolean).join('\n').toLowerCase();
            return haystack.includes(normalizedQuery);
        });
    }, [filter, issueKeys, query, rows]);

    const rowVirtualizer = useVirtualizer({
        count: filteredRows.length,
        getScrollElement: () => scrollRef.current,
        getItemKey: index => filteredRows[index]?.entry_id || index,
        estimateSize: index => filteredRows[index]?.row_type === 'translation' ? 104 : 64,
        overscan: 8,
        initialOffset: initialScrollOffset || 0,
    });

    useEffect(() => {
        if (!focusEntryKey) {
            handledFocusRef.current = null;
            return undefined;
        }
        if (handledFocusRef.current === focusEntryKey) return undefined;
        const index = filteredRows.findIndex(row => row.row_type === 'translation' && row.key === focusEntryKey);
        if (index < 0) return undefined;
        handledFocusRef.current = focusEntryKey;
        setHighlightedEntryKey(focusEntryKey);
        rowVirtualizer.scrollToIndex(index, { align: 'center' });
        const focusTimer = setTimeout(() => {
            const rowElement = [...document.querySelectorAll('[data-proofreading-entry="true"]')]
                .find(element => element.dataset.entryKey === focusEntryKey);
            rowElement?.querySelector('textarea')?.focus();
        }, 80);
        const highlightTimer = setTimeout(() => setHighlightedEntryKey(null), 2400);
        return () => {
            clearTimeout(focusTimer);
            clearTimeout(highlightTimer);
        };
    }, [filteredRows, focusEntryKey, rowVirtualizer]);

    useEffect(() => () => {
        if (scrollFrameRef.current) cancelAnimationFrame(scrollFrameRef.current);
    }, []);

    const handleScroll = event => {
        const nextOffset = event.currentTarget.scrollTop;
        if (scrollFrameRef.current) return;
        scrollFrameRef.current = requestAnimationFrame(() => {
            scrollFrameRef.current = null;
            onScrollOffsetChange?.(nextOffset);
        });
    };

    const getLineLabel = row => row.line_end && row.line_end !== row.line_start
        ? `L${row.line_start}-${row.line_end}`
        : `L${row.line_number}`;

    const renderStructureRow = row => {
        const isComment = row.structure_type === 'comment';
        const isBlank = row.structure_type === 'blank';
        const lineCount = (row.line_end || row.line_number) - (row.line_start || row.line_number) + 1;

        return (
            <div className={`${classes.row} ${classes.structureRow}`}>
                <div className={classes.keyCell}>
                    <Group gap={6} wrap="nowrap">
                        <Badge size="sm" variant="light" color={isComment ? 'teal' : 'gray'} leftSection={<IconCode size={12} />}>
                            {t(`proofreading.structure.${row.structure_type}`, { defaultValue: row.structure_type })}
                        </Badge>
                        <Text size="sm" c="dimmed" ff="monospace">{getLineLabel(row)}</Text>
                    </Group>
                </div>

                {isComment ? (
                    <>
                        <div className={classes.cell}>
                            <Text className={classes.commentText}>{row.source_value}</Text>
                        </div>
                        <div className={`${classes.cell} ${classes.mutedCell}`}>
                            <Text size="sm" c="dimmed">{t('proofreading.not_applicable')}</Text>
                        </div>
                        <div className={classes.cell}>
                            <Textarea
                                aria-label={t('proofreading.edit_comment')}
                                value={row.final_value || ''}
                                onChange={event => onFinalValueChange(row.entry_id, event.currentTarget.value)}
                                autosize
                                minRows={Math.min(2, lineCount)}
                                size="sm"
                                classNames={{ input: classes.commentInput }}
                            />
                        </div>
                    </>
                ) : (
                    <div className={`${classes.cell} ${classes.structureContent}`}>
                        <Text size="sm" ff="monospace" c={isBlank ? 'dimmed' : 'gray.3'}>
                            {isBlank
                                ? t('proofreading.blank_lines', { count: lineCount })
                                : row.display_text}
                        </Text>
                    </div>
                )}
            </div>
        );
    };

    const renderTranslationRow = row => {
        const hasIssue = issueKeys.has(row.key);
        const changed = isProofreadingRowChanged(row);
        return (
            <div className={`${classes.row} ${changed ? classes.changedRow : ''}`}>
                <div className={classes.keyCell}>
                    <Group gap={6} wrap="nowrap" align="flex-start">
                        <IconHash size={15} className={classes.keyIcon} />
                        <div className={classes.keyDetails}>
                            <Text size="sm" ff="monospace" className={classes.keyText}>{row.key}</Text>
                            <Group gap={5} mt={6}>
                                <Badge size="sm" variant="light" color="gray">L{row.line_number}</Badge>
                                {changed && <Badge size="sm" variant="light" color="blue">{t('proofreading.changed')}</Badge>}
                                {hasIssue && (
                                    <Tooltip label={t('proofreading.validation_issue')}>
                                        <Badge size="sm" color="yellow" leftSection={<IconAlertTriangle size={12} />}>
                                            {t('proofreading.issue')}
                                        </Badge>
                                    </Tooltip>
                                )}
                            </Group>
                        </div>
                    </Group>
                </div>
                <div className={classes.cell}>
                    <Text className={classes.readonlyText}>{row.source_value}</Text>
                </div>
                <div className={classes.cell}>
                    <Text className={classes.readonlyText}>{row.ai_value}</Text>
                </div>
                <div className={classes.cell}>
                    <Textarea
                        aria-label={t('proofreading.edit_final', { key: row.key })}
                        value={row.final_value || ''}
                        onChange={event => onFinalValueChange(row.entry_id, event.currentTarget.value)}
                        onFocus={() => onFocusedEntryChange?.(row.key)}
                        autosize
                        minRows={2}
                        size="sm"
                        classNames={{ input: classes.finalInput }}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className={classes.root}>
            <Group justify="space-between" gap="sm" p="sm" className={classes.toolbar}>
                <TextInput
                    leftSection={<IconSearch size={17} />}
                    value={query}
                    onChange={event => onQueryChange(event.currentTarget.value)}
                    placeholder={t('proofreading.search')}
                    size="sm"
                    className={classes.search}
                />
                <SegmentedControl
                    value={filter}
                    onChange={onFilterChange}
                    size="sm"
                    data={[
                        { value: 'all', label: t('proofreading.filter.all') },
                        { value: 'changed', label: t('proofreading.filter.changed') },
                        { value: 'issues', label: t('proofreading.filter.issues') },
                    ]}
                />
            </Group>

            <div ref={scrollRef} onScroll={handleScroll} className={classes.scrollArea} style={{ opacity: loading ? 0.55 : 1 }}>
                <div className={`${classes.row} ${classes.headerRow}`}>
                    <ColumnHeader label={t('proofreading.columns.key')} description={t('proofreading.hint.key')} />
                    <ColumnHeader label={t('proofreading.columns.source')} description={t('proofreading.hint.original_source')} />
                    <ColumnHeader label={t('proofreading.columns.ai_draft')} description={t('proofreading.hint.ai_source')} />
                    <ColumnHeader label={t('proofreading.columns.final')} description={t('proofreading.hint.final_source')} />
                </div>

                {filteredRows.length === 0 ? (
                    <Text ta="center" c="dimmed" py="xl">{t('proofreading.no_entries')}</Text>
                ) : (
                    <div className={classes.virtualCanvas} style={{ height: rowVirtualizer.getTotalSize() }}>
                        {rowVirtualizer.getVirtualItems().map(virtualRow => {
                            const row = filteredRows[virtualRow.index];
                            return (
                                <div
                                    key={row.entry_id}
                                    data-index={virtualRow.index}
                                    ref={rowVirtualizer.measureElement}
                                    className={`${classes.virtualRow} ${row.key === highlightedEntryKey ? classes.highlightedRow : ''}`}
                                    data-proofreading-entry={row.row_type === 'translation' ? 'true' : undefined}
                                    data-entry-key={row.key || undefined}
                                    style={{ transform: `translateY(${virtualRow.start}px)` }}
                                >
                                    {row.row_type === 'translation'
                                        ? renderTranslationRow(row)
                                        : renderStructureRow(row)}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ProofreadingEntryWorkspace;
