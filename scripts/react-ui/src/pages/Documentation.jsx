import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Grid, Title, Select, Loader, Paper, ScrollArea, NavLink, Box, Group, Text } from '@mantine/core';
import { IconFileText, IconFolder, IconFolderOpen } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import api from '../utils/api';

// Map language codes to their display names for a better UI.
const languageNameMap = {
    en: 'English',
    zh: '中文',
};

const getLanguageName = (code) => {
    return languageNameMap[code] || code; // Fallback to the code itself if no mapping exists
};


const fetchDocLanguages = async () => {
    try {
        const response = await api.get('/api/docs-languages');
        return response.data;
    } catch (error) {
        console.error("Failed to fetch doc languages:", error);
        return ['en']; // Fallback to 'en'
    }
};

const fetchDocTree = async () => {
    try {
        const response = await api.get('/api/docs-tree');
        return response.data;
    } catch (error) {
        console.error("Failed to fetch doc tree:", error);
        return {}; // Return empty object on error
    }
};

const fetchDocContent = async (path) => {
    if (!path) return 'No file selected.';
    console.log(`Fetching content from API for path: ${path}`);
    try {
        const response = await api.get('/api/doc-content', {
            params: { path: path }
        });
        return response.data;
    } catch (error) {
        console.error(`Failed to fetch doc content for path ${path}:`, error);
        return 'Content could not be loaded. Please check the console for more details.';
    }
};

import styles from './Documentation.module.css';

// ... imports ...

const Documentation = () => {
    // ... existing state ...
    const { t, i18n } = useTranslation();
    const [availableLangs, setAvailableLangs] = useState([]);
    const [selectedLang, setSelectedLang] = useState('');
    const [fullTreeData, setFullTreeData] = useState({});
    const [treeData, setTreeData] = useState([]);
    const [treeLoading, setTreeLoading] = useState(true);

    const [selectedFile, setSelectedFile] = useState('');
    const [content, setContent] = useState('');
    const [contentLoading, setContentLoading] = useState(true);

    // ... effects ...
    // Effect for fetching languages and the entire directory tree on component mount
    useEffect(() => {
        setTreeLoading(true);
        Promise.all([fetchDocLanguages(), fetchDocTree()]).then(([langs, tree]) => {
            setAvailableLangs(langs);
            const initialLang = langs.includes(i18n.language) ? i18n.language : (langs[0] || 'en');
            setSelectedLang(initialLang);

            setFullTreeData(tree);
            setTreeData(tree[initialLang] || []);

            // Set a default file to display initially
            const defaultFile = `${initialLang}/index.md`;
            setSelectedFile(defaultFile);

            setTreeLoading(false);
        });
    }, [i18n.language]);

    // Effect for updating the displayed tree when language changes
    useEffect(() => {
        if (!treeLoading) { // Avoid running on initial load before fullTreeData is set
            setTreeData(fullTreeData[selectedLang] || []);
        }
    }, [selectedLang, fullTreeData, treeLoading]);

    // Effect for fetching file content when selectedFile changes
    useEffect(() => {
        if (selectedFile) {
            setContentLoading(true);
            fetchDocContent(selectedFile).then(data => {
                setContent(data);
                setContentLoading(false);
            });
        } else {
            setContent('');
        }
    }, [selectedFile]);

    const handleSelect = (key) => {
        setSelectedFile(key);
    };

    // Recursive component to render the file tree using Mantine NavLink
    const FileTree = ({ nodes, onSelect, selectedKey, level = 0 }) => {
        return (
            <>
                {nodes.map(node => {
                    if (node.isLeaf) {
                        return (
                            <NavLink
                                key={node.key}
                                label={node.title}
                                leftSection={<IconFileText size="1rem" stroke={1.5} />}
                                active={node.key === selectedKey}
                                onClick={() => onSelect(node.key)}
                                className={styles.navLink}
                                variant="subtle"
                            />
                        );
                    } else {
                        return (
                            <NavLink
                                key={node.key}
                                label={node.title}
                                leftSection={<IconFolder size="1rem" stroke={1.5} />}
                                childrenOffset={28}
                                defaultOpened={true} // Default to opened for better visibility
                                className={styles.navLink}
                                variant="subtle"
                            >
                                {node.children && (
                                    <FileTree
                                        nodes={node.children}
                                        onSelect={onSelect}
                                        selectedKey={selectedKey}
                                        level={level + 1}
                                    />
                                )}
                            </NavLink>
                        );
                    }
                })}
            </>
        );
    };

    return (
        <div className={styles.container}>
            {/* Left Sidebar: Documentation Navigation */}
            <div className={styles.sidebarWrapper}>
                <Paper p="md" className={styles.sidebar}>
                    <Group justify="space-between" mb="md">
                        <Title order={4} style={{ fontFamily: 'var(--font-header)', color: 'var(--text-highlight)' }}>{t('doc_nav_title')}</Title>
                    </Group>

                    <Select
                        value={selectedLang}
                        onChange={setSelectedLang}
                        data={availableLangs.map(lang => ({ value: lang, label: getLanguageName(lang) }))}
                        disabled={!availableLangs.length}
                        mb="md"
                        allowDeselect={false}
                    />

                    <ScrollArea style={{ flex: 1 }} type="auto">
                        {treeLoading ? (
                            <div style={{ textAlign: 'center', marginTop: '20px' }}><Loader size="sm" /></div>
                        ) : (
                            <Box>
                                <FileTree nodes={treeData} onSelect={handleSelect} selectedKey={selectedFile} />
                            </Box>
                        )}
                    </ScrollArea>
                </Paper>
            </div>

            {/* Right Content: Documentation Viewer */}
            <div className={styles.contentWrapper}>
                <Paper p="xl" className={styles.content}>
                    {contentLoading ? (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                            <Loader size="xl" />
                        </div>
                    ) : (
                        <div className="markdown-body" style={{ color: 'var(--text-main)' }}>
                            <ReactMarkdown rehypePlugins={[rehypeRaw]}>
                                {content}
                            </ReactMarkdown>
                        </div>
                    )}
                </Paper>
            </div>
        </div>
    );
};

export default Documentation;
