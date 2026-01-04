import React, { useState, useEffect } from 'react';
import { Modal, Text, Group, Button } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import api from '../../utils/api';
import { useSidebar } from '../../context/SidebarContext';

import ProjectHeader from '../project/ProjectHeader';
import ProjectNoteList from '../project/ProjectNoteList';
import ProjectPathManager from '../project/ProjectPathManager';
import ProjectFileList from '../project/ProjectFileList';
import ProjectSidebar from '../project/ProjectSidebar';

const ProjectOverview = ({ projectDetails, handleStatusChange, handleProofread, onFileStatusChange, onPathsUpdated, onDeleteForever, onManageProject }) => {
    const { t } = useTranslation();
    const [notes, setNotes] = useState(''); // Current input for new note
    const [deleteModalOpen, setDeleteModalOpen] = useState(false);
    const [deleteNoteId, setDeleteNoteId] = useState(null);
    const [refreshSidebarTrigger, setRefreshSidebarTrigger] = useState(0);

    // Sidebar Context
    const { setSidebarContent, setSidebarWidth, sidebarWidth, setSidebarCollapsed } = useSidebar();

    // Cleanup sidebar on unmount
    useEffect(() => {
        return () => {
            setSidebarContent(null);
        };
    }, []);

    const handleViewNotesHistory = () => {
        // Auto-expand sidebar if collapsed or too narrow
        if (!sidebarWidth || sidebarWidth < 300) {
            setSidebarWidth(350);
        }
        setSidebarCollapsed(false); // Expand sidebar
        setSidebarContent(
            <ProjectSidebar
                projectId={projectDetails.project_id}
                onDeleteNote={handleDeleteNote}
                key={refreshSidebarTrigger} // Force re-render to refresh list
            />
        );
    };

    // Refresh sidebar when trigger changes
    useEffect(() => {
        if (sidebarWidth > 0) { // Only if sidebar is likely open/active
            handleViewNotesHistory();
        }
    }, [refreshSidebarTrigger]);


    const onSaveNote = async () => {
        if (!notes.trim()) return;
        try {
            await api.post(`/api/project/${projectDetails.project_id}/notes`, { notes });
            setNotes(''); // Clear input
            setRefreshSidebarTrigger(prev => prev + 1); // Trigger sidebar refresh
        } catch (error) {
            console.error("Failed to save note", error);
            alert("Failed to save note");
        }
    };

    const handleDeleteNote = (noteId) => {
        setDeleteNoteId(noteId);
        setDeleteModalOpen(true);
    };

    const confirmDeleteNote = async () => {
        if (!deleteNoteId) return;
        try {
            await api.delete(`/api/project/${projectDetails.project_id}/notes/${deleteNoteId}`);
            setDeleteModalOpen(false);
            setDeleteNoteId(null);
            setRefreshSidebarTrigger(prev => prev + 1); // Trigger sidebar refresh
        } catch (error) {
            console.error("Failed to delete note", error);
            alert("Failed to delete note");
        }
    };

    if (!projectDetails) return null;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', gap: '1rem' }}>
            {/* Header section with stats */}
            <div style={{ flexShrink: 0 }}>
                <ProjectHeader
                    projectDetails={projectDetails}
                    handleStatusChange={handleStatusChange}
                    onDeleteForever={onDeleteForever}
                    onManageProject={onManageProject}
                />

                <ProjectNoteList
                    notes={notes}
                    setNotes={setNotes}
                    onSaveNote={onSaveNote}
                    onViewHistory={handleViewNotesHistory}
                />

                <ProjectPathManager
                    projectDetails={projectDetails}
                    onPathsUpdated={onPathsUpdated}
                />
            </div>

            {/* Scrollable file list */}
            <ProjectFileList
                projectDetails={projectDetails}
                handleProofread={handleProofread}
                onFileStatusChange={onFileStatusChange}
            />

            {/* Delete Note Confirmation Modal */}
            <Modal
                opened={deleteModalOpen}
                onClose={() => setDeleteModalOpen(false)}
                title={t('project_management.delete_note_confirm_title')}
                centered
            >
                <Text size="sm">{t('project_management.delete_note_confirm_content')}</Text>
                <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={() => setDeleteModalOpen(false)}>
                        {t('button_cancel')}
                    </Button>
                    <Button color="red" onClick={confirmDeleteNote}>
                        {t('project_management.delete_note')}
                    </Button>
                </Group>
            </Modal>
        </div>
    );
};

export default ProjectOverview;
