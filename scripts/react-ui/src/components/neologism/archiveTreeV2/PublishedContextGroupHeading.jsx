import React, { useState } from 'react';
import { Badge, Button } from '@mantine/core';
import { IconCheck, IconPencil, IconTrash, IconX } from '@tabler/icons-react';

import styles from './PublishedContextWorkbench.module.css';

const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });

const PublishedContextGroupHeading = ({
    group,
    fragmentCount,
    focused,
    kicker,
    onSelectGroup,
    onRenameGroup,
    onDeleteGroup,
    t,
}) => {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(group.label);
    const [confirmDelete, setConfirmDelete] = useState(false);

    const cancelRename = () => {
        setDraft(group.label);
        setEditing(false);
    };
    const commitRename = () => {
        const label = draft.trim();
        if (!label) return;
        if (label !== group.label) onRenameGroup?.(group.id, label);
        setEditing(false);
    };
    const handleRenameKeyDown = (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            commitRename();
            return;
        }
        if (event.key === 'Escape') {
            event.preventDefault();
            cancelRename();
        }
    };

    return (
        <div className={styles.groupHeadingRow}>
            {editing ? (
                <form
                    className={styles.groupRenameForm}
                    onSubmit={(event) => {
                        event.preventDefault();
                        commitRename();
                    }}
                >
                    <span className={styles.groupKicker}>{kicker}</span>
                    <label className={styles.groupRenameLabel}>
                        <span className={styles.visuallyHidden}>
                            {text(t, 'mod_archive.tree_v2.rename_group_input', 'Event chain name')}
                        </span>
                        <input
                            className={styles.groupRenameInput}
                            aria-label={text(t, 'mod_archive.tree_v2.rename_group_input', 'Event chain name')}
                            value={draft}
                            onChange={(event) => setDraft(event.currentTarget.value)}
                            onKeyDown={handleRenameKeyDown}
                            autoFocus
                        />
                    </label>
                    {group.summary && <span className={styles.groupSummary}>{group.summary}</span>}
                    <div className={styles.groupRenameActions}>
                        <Button
                            type="submit"
                            size="compact-xs"
                            variant="light"
                            aria-label={text(t, 'mod_archive.tree_v2.save_group_name', 'Save event chain name')}
                            disabled={!draft.trim()}
                        >
                            <IconCheck size={15} aria-hidden="true" />
                        </Button>
                        <Button
                            type="button"
                            size="compact-xs"
                            variant="default"
                            aria-label={text(t, 'cancel', 'Cancel')}
                            onClick={cancelRename}
                        >
                            <IconX size={15} aria-hidden="true" />
                        </Button>
                    </div>
                </form>
            ) : (
                <button
                    type="button"
                    className={styles.groupHeadingButton}
                    data-testid={`published-context-group-header-${group.id}`}
                    onClick={() => onSelectGroup?.(group.id)}
                >
                    <span className={styles.groupHeadingCopy}>
                        <span className={styles.groupKicker}>{kicker}</span>
                        <span className={styles.groupTitle}>{group.label}</span>
                        {focused && group.summary && <span className={styles.groupSummary}>{group.summary}</span>}
                    </span>
                    <Badge className={styles.groupCount} size="sm" variant={focused ? 'light' : 'outline'}>{fragmentCount}</Badge>
                </button>
            )}
            {focused && !editing && onRenameGroup && (
                <Button
                    className={styles.groupRenameButton}
                    size="compact-xs"
                    variant="subtle"
                    aria-label={text(t, 'mod_archive.tree_v2.rename_group', 'Rename event chain')}
                    onClick={() => {
                        setDraft(group.label);
                        setEditing(true);
                    }}
                >
                    <IconPencil size={15} aria-hidden="true" />
                </Button>
            )}
            {focused && !editing && onDeleteGroup && (
                confirmDelete ? (
                    <div className={styles.groupDeleteConfirm}>
                        <Button size="compact-xs" color="red" onClick={() => onDeleteGroup(group.id)}>
                            {text(t, 'mod_archive.tree_v2.confirm_delete_group', 'Delete chain')}
                        </Button>
                        <Button size="compact-xs" variant="default" onClick={() => setConfirmDelete(false)}>
                            {text(t, 'cancel', 'Cancel')}
                        </Button>
                    </div>
                ) : (
                    <Button
                        size="compact-xs"
                        color="red"
                        variant="subtle"
                        aria-label={text(t, 'mod_archive.tree_v2.delete_group', 'Delete event chain')}
                        data-testid={`published-context-delete-group-${group.id}`}
                        onClick={() => setConfirmDelete(true)}
                    >
                        <IconTrash size={15} aria-hidden="true" />
                    </Button>
                )
            )}
        </div>
    );
};

export default PublishedContextGroupHeading;
