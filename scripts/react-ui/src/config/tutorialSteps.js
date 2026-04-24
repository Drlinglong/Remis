/**
 * Tutorial steps configuration
 */
export const getTutorialSteps = (t, pageName) => {
    const steps = {
        home: [
            {
                element: '#welcome-banner',
                popover: {
                    title: t('tutorial.home.welcome.title'),
                    description: t('tutorial.home.welcome.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#stat-cards',
                popover: {
                    title: t('tutorial.home.stats.title'),
                    description: t('tutorial.home.stats.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#recent-activity',
                popover: {
                    title: t('tutorial.home.activity.title'),
                    description: t('tutorial.home.activity.desc'),
                    side: "left",
                    align: 'start'
                }
            },
            {
                element: '#quick-links',
                popover: {
                    title: t('tutorial.home.quick_links.title'),
                    description: t('tutorial.home.quick_links.desc'),
                    side: "left",
                    align: 'start'
                }
            },
            {
                element: '#sidebar-nav',
                popover: {
                    title: t('tutorial.home.navigation.title'),
                    description: t('tutorial.home.navigation.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#nav-settings',
                popover: {
                    title: t('tutorial.home.settings_link.title'),
                    description: t('tutorial.home.settings_link.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#tutorial-sidebar-link',
                popover: {
                    title: t('tutorial.home.tutorial_btn.title'),
                    description: t('tutorial.home.tutorial_btn.desc'),
                    side: "right",
                    align: 'start'
                }
            }
        ],
        'settings': [
            {
                element: '#settings-tab-general',
                popover: {
                    title: t('tutorial.settings.general.title'),
                    description: t('tutorial.settings.general.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#settings-theme-group',
                popover: {
                    title: t('tutorial.settings.theme.title'),
                    description: t('tutorial.settings.theme.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#settings-tab-version',
                popover: {
                    title: t('tutorial.settings.version.title'),
                    description: t('tutorial.settings.version.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#settings-tab-api',
                popover: {
                    title: t('tutorial.settings.api.title'),
                    description: t('tutorial.settings.api.desc'),
                    side: "bottom",
                    align: 'start'
                }
            }
        ],
        'settings-api': [
            {
                element: '#api-storage-info',
                popover: {
                    title: t('tutorial.settings.api_guide.title'),
                    description: t('tutorial.settings.api_guide.desc'),
                    side: "bottom",
                    align: 'center'
                }
            },
            {
                element: '#api-providers-accordion',
                popover: {
                    title: t('tutorial.settings.api.title'),
                    description: t('tutorial.settings.api.desc'),
                    side: "bottom",
                    align: 'center'
                }
            },
            {
                element: '#api-providers-accordion',
                popover: {
                    title: t('tutorial.settings.api_regions.title'),
                    description: t('tutorial.settings.api_regions.desc'),
                    side: "bottom",
                    align: 'center'
                }
            },
            {
                element: '#api-provider-card-gemini',
                popover: {
                    title: t('tutorial.settings.api_provider.title'),
                    description: t('tutorial.settings.api_provider.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#api-provider-card-gemini',
                popover: {
                    title: t('tutorial.settings.api_cost.title'),
                    description: t('tutorial.settings.api_cost.desc'),
                    side: "right",
                    align: 'start'
                }
            }
        ],
        'tools': [
            {
                element: '#thumbnail-toolbox',
                popover: {
                    title: t('tutorial.tools.thumbnail.toolbox.title'),
                    description: t('tutorial.tools.thumbnail.toolbox.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#thumbnail-upload-area',
                popover: {
                    title: t('tutorial.tools.thumbnail.drag.title'),
                    description: t('tutorial.tools.thumbnail.drag.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'project-management': [ // Fallback
            {
                element: '#project-list-container',
                popover: {
                    title: t('tutorial.project_management.list.title'),
                    description: t('tutorial.project_management.list.desc'),
                    side: "bottom",
                    align: 'center'
                }
            }
        ],
        'project-management-list': [
            {
                element: '#create-project-btn',
                popover: {
                    title: t('tutorial.project_management.create.title'),
                    description: t('tutorial.project_management.create.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#project-list-container',
                popover: {
                    title: t('tutorial.project_management.list.title'),
                    description: t('tutorial.project_management.list.desc'),
                    side: "bottom",
                    align: 'center'
                }
            }
        ],
        'project-management-dashboard': [
            {
                element: '#project-stats-grid',
                popover: {
                    title: t('tutorial.project_management.stats.title'),
                    description: t('tutorial.project_management.stats.desc'),
                    side: "bottom",
                    align: 'center'
                }
            },
            {
                element: '#start-translation-btn',
                popover: {
                    title: t('tutorial.project_management.start.title'),
                    description: t('tutorial.project_management.start.desc'),
                    side: "left",
                    align: 'center'
                }
            },
            {
                element: '#manage-paths-btn',
                popover: {
                    title: t('tutorial.project_management.paths.title'),
                    description: t('tutorial.project_management.paths.desc'),
                    side: "bottom",
                    align: 'end'
                }
            },
            {
                element: '#kanban-tab-control',
                popover: {
                    title: t('tutorial.project_management.tabs.title'),
                    description: t('tutorial.project_management.tabs.desc'),
                    side: "bottom",
                    align: 'center'
                }
            }
        ],
        'project-management-validation': [
            {
                element: '#project-validation-scope-alert',
                popover: {
                    title: t('tutorial.project_management.validation_scope.title'),
                    description: t('tutorial.project_management.validation_scope.desc'),
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '#project-validation-open-workshop-btn',
                popover: {
                    title: t('tutorial.project_management.validation_workshop.title'),
                    description: t('tutorial.project_management.validation_workshop.desc'),
                    side: "left",
                    align: 'center'
                }
            }
        ],
        'project-management-history': [
            {
                element: '#project-history-current-state',
                popover: {
                    title: t('tutorial.project_management.history_overview.title'),
                    description: t('tutorial.project_management.history_overview.desc'),
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '#project-history-upload-btn',
                popover: {
                    title: t('tutorial.project_management.history_upload.title'),
                    description: t('tutorial.project_management.history_upload.desc'),
                    side: "left",
                    align: 'center'
                }
            },
            {
                element: '#project-history-incremental-btn',
                popover: {
                    title: t('tutorial.project_management.history_incremental.title'),
                    description: t('tutorial.project_management.history_incremental.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'translation-step-0': [
            {
                element: '#translation-project-list',
                popover: {
                    title: t('tutorial.translation.select.title'),
                    description: t('tutorial.translation.select.desc'),
                    side: "bottom",
                    align: 'center'
                }
            }
        ],
        'translation-step-1': [
            {
                element: '#translation-config-card',
                popover: {
                    title: t('tutorial.translation.config.title'),
                    description: t('tutorial.translation.config.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#translation-start-btn',
                popover: {
                    title: t('tutorial.translation.start.title'),
                    description: t('tutorial.translation.start.desc'),
                    side: "top",
                    align: 'end'
                }
            }
        ],
        'translation-step-2': [
            {
                element: '#task-runner-container',
                popover: {
                    title: t('tutorial.translation.processing.title'),
                    description: t('tutorial.translation.processing.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'incremental-translation-step-0': [
            {
                element: '#incremental-project-selector',
                popover: {
                    title: t('tutorial.incremental_translation.select.title'),
                    description: t('tutorial.incremental_translation.select.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#incremental-project-grid',
                popover: {
                    title: t('tutorial.incremental_translation.project_cards.title'),
                    description: t('tutorial.incremental_translation.project_cards.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'incremental-translation-step-1': [
            {
                element: '#incremental-setup-card',
                popover: {
                    title: t('tutorial.incremental_translation.setup.title'),
                    description: t('tutorial.incremental_translation.setup.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#incremental-target-languages',
                popover: {
                    title: t('tutorial.incremental_translation.languages.title'),
                    description: t('tutorial.incremental_translation.languages.desc'),
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '#incremental-folder-picker',
                popover: {
                    title: t('tutorial.incremental_translation.folder.title'),
                    description: t('tutorial.incremental_translation.folder.desc'),
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '#incremental-embedded-workshop',
                popover: {
                    title: t('tutorial.incremental_translation.workshop.title'),
                    description: t('tutorial.incremental_translation.workshop.desc'),
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '#incremental-run-prescan-btn',
                popover: {
                    title: t('tutorial.incremental_translation.prescan.title'),
                    description: t('tutorial.incremental_translation.prescan.desc'),
                    side: "top",
                    align: 'end'
                }
            }
        ],
        'incremental-translation-step-2': [
            {
                element: '#incremental-prescan-summary',
                popover: {
                    title: t('tutorial.incremental_translation.summary.title'),
                    description: t('tutorial.incremental_translation.summary.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#incremental-start-run-btn',
                popover: {
                    title: t('tutorial.incremental_translation.start.title'),
                    description: t('tutorial.incremental_translation.start.desc'),
                    side: "top",
                    align: 'end'
                }
            }
        ],
        'incremental-translation-step-3': [
            {
                element: '#incremental-execution-panel',
                popover: {
                    title: t('tutorial.incremental_translation.execution.title'),
                    description: t('tutorial.incremental_translation.execution.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#incremental-final-summary',
                popover: {
                    title: t('tutorial.incremental_translation.results.title'),
                    description: t('tutorial.incremental_translation.results.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'glossary-manager': [
            {
                element: '#glossary-search',
                popover: {
                    title: t('tutorial.glossary.search.title'),
                    description: t('tutorial.glossary.search.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#glossary-file-list',
                popover: {
                    title: t('tutorial.glossary.files.title'),
                    description: t('tutorial.glossary.files.desc'),
                    side: "right",
                    align: 'start'
                }
            },
            {
                element: '#glossary-entries-table',
                popover: {
                    title: t('tutorial.glossary.table.title'),
                    description: t('tutorial.glossary.table.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'agent-workshop-step-0': [
            {
                element: '#agent-workshop-project-selector',
                popover: {
                    title: t('tutorial.agent_workshop.select.title'),
                    description: t('tutorial.agent_workshop.select.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#agent-workshop-project-grid',
                popover: {
                    title: t('tutorial.agent_workshop.project_cards.title'),
                    description: t('tutorial.agent_workshop.project_cards.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'agent-workshop-step-1': [
            {
                element: '#agent-workshop-project-summary',
                popover: {
                    title: t('tutorial.agent_workshop.summary.title'),
                    description: t('tutorial.agent_workshop.summary.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#agent-workshop-scan-btn',
                popover: {
                    title: t('tutorial.agent_workshop.scan.title'),
                    description: t('tutorial.agent_workshop.scan.desc'),
                    side: "left",
                    align: 'center'
                }
            }
        ],
        'agent-workshop-step-2': [
            {
                element: '#agent-workshop-fix-settings',
                popover: {
                    title: t('tutorial.agent_workshop.fix_settings.title'),
                    description: t('tutorial.agent_workshop.fix_settings.desc'),
                    side: "bottom",
                    align: 'center'
                }
            },
            {
                element: '#agent-workshop-issue-details',
                popover: {
                    title: t('tutorial.agent_workshop.issue_details.title'),
                    description: t('tutorial.agent_workshop.issue_details.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#agent-workshop-start-fix-btn',
                popover: {
                    title: t('tutorial.agent_workshop.start.title'),
                    description: t('tutorial.agent_workshop.start.desc'),
                    side: "top",
                    align: 'end'
                }
            }
        ],
        'agent-workshop-step-3': [
            {
                element: '#agent-workshop-execution-panel',
                popover: {
                    title: t('tutorial.agent_workshop.execution.title'),
                    description: t('tutorial.agent_workshop.execution.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#agent-workshop-diff-preview',
                popover: {
                    title: t('tutorial.agent_workshop.results.title'),
                    description: t('tutorial.agent_workshop.results.desc'),
                    side: "top",
                    align: 'center'
                }
            }
        ],
        'proofreading': [
            {
                element: '#proofreading-mod-select',
                popover: {
                    title: t('tutorial.proofreading.mod_select.title'),
                    description: t('tutorial.proofreading.mod_select.desc'),
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#proofreading-main-content',
                popover: {
                    title: t('tutorial.proofreading.editor.title'),
                    description: t('tutorial.proofreading.editor.desc'),
                    side: "top",
                    align: 'center'
                }
            },
            {
                element: '#proofreading-validate-btn',
                popover: {
                    title: t('tutorial.proofreading.validate.title'),
                    description: t('tutorial.proofreading.validate.desc'),
                    side: "left",
                    align: 'start'
                }
            }
        ]
    };

    return steps[pageName] || [];
};
