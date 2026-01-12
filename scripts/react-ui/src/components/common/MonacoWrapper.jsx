import React, { useRef, useEffect } from 'react';
import Editor, { loader } from '@monaco-editor/react';
import { useMantineTheme } from '@mantine/core';

// Ensure Monaco loads from CDN or local if configured
// loader.config({ paths: { vs: '...' } }); 

const MonacoWrapper = ({
    value,
    onChange,
    language = 'yaml',
    readOnly = false,
    theme = 'vs-dark', // 'vs-dark' or 'light'
    height = '100%',
    scrollRef // Optional ref to expose editor instance for sync scrolling
}) => {
    const editorRef = useRef(null);
    const mantineTheme = useMantineTheme();

    const handleEditorDidMount = (editor, monaco) => {
        editorRef.current = editor;

        // Expose the editor instance via ref if provided
        if (scrollRef) {
            scrollRef.current = editor;
        }

        // Register custom language for Paradox localization files
        if (!monaco.languages.getLanguages().some(lang => lang.id === 'paradox-loc')) {
            monaco.languages.register({ id: 'paradox-loc' });

            monaco.languages.setMonarchTokensProvider('paradox-loc', {
                tokenizer: {
                    root: [
                        // Comments
                        [/#.*$/, 'comment'],

                        // Language header (e.g., l_english:, l_simp_chinese:)
                        [/^\s*l_[a-z_]+\s*:/, 'keyword'],

                        // Key with version number (e.g., key:0, key:1)
                        [/^\s*[a-zA-Z_][a-zA-Z0-9_]*:[0-9]+/, 'variable.name'],

                        // Strings with proper Unicode support (including Chinese characters)
                        // This regex matches any text within double quotes, including Unicode
                        [/"([^"\\]|\\.)*"/, 'string'],

                        // Color codes and special markers
                        [/\$[a-zA-Z_][a-zA-Z0-9_]*\$/, 'type'],
                        [/§[a-zA-Z!]/, 'type'],

                        // Format tags (e.g., [concept_images])
                        [/\[[^\]]+\]/, 'keyword'],

                        // Scope markers
                        [/\{/, '@brackets'],
                        [/\}/, '@brackets'],
                    ],
                },
            });

            // Define theme colors for better visibility
            monaco.editor.defineTheme('paradox-dark', {
                base: 'vs-dark',
                inherit: true,
                rules: [
                    { token: 'comment', foreground: '6A9955' },
                    { token: 'keyword', foreground: 'C586C0' },
                    { token: 'variable.name', foreground: '9CDCFE' },
                    { token: 'string', foreground: 'CE9178' }, // Orange-ish color for strings
                    { token: 'type', foreground: '4EC9B0' }, // Teal for special markers
                ],
                colors: {
                    'editor.background': '#1E1E1E',
                    'editor.foreground': '#D4D4D4',
                    'editorLineNumber.foreground': '#858585',
                    'editor.selectionBackground': '#264F78',
                    'editor.inactiveSelectionBackground': '#3A3D41'
                }
            });
        }
    };

    // Handle resizing
    useEffect(() => {
        const handleResize = () => {
            if (editorRef.current) {
                editorRef.current.layout();
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // 暂时直接使用 vs-dark 测试背景色
    const effectiveLanguage = language === 'yaml' ? 'paradox-loc' : language;
    const effectiveTheme = 'vs-dark';

    return (
        <div style={{ height: height, width: '100%', overflow: 'hidden' }}>
            <Editor
                height="100%"
                defaultLanguage={effectiveLanguage}
                value={value}
                onChange={onChange}
                theme={effectiveTheme}
                onMount={handleEditorDidMount}
                options={{
                    readOnly: readOnly,
                    wordWrap: 'on', // Enable auto-wrapping
                    minimap: { enabled: false }, // Disable minimap for cleaner look in columns
                    scrollBeyondLastLine: false,
                    fontSize: 13,
                    fontFamily: 'Consolas, "Courier New", monospace',
                    lineNumbers: 'on',
                    renderWhitespace: 'selection',
                    automaticLayout: true, // Auto-resize
                    padding: { top: 10, bottom: 10 },
                    scrollbar: {
                        vertical: 'visible',
                        horizontal: 'hidden', // Hide horizontal scrollbar since we wrap
                        useShadows: false,
                        verticalScrollbarSize: 10
                    },
                    unicodeHighlight: {
                        ambiguousCharacters: false,
                        invisibleCharacters: false,
                    }
                }}
            />
        </div>
    );
};

export default MonacoWrapper;
