/**
 * Developer feature master switch.
 * Keep this false for normal user-facing builds.
 */
const ENABLE_EXPERIMENTAL_FEATURES = false;
export const BUILD_CHANNEL = import.meta.env.VITE_REMIS_BUILD_CHANNEL || 'stable';
export const IS_AGENT_PREVIEW = BUILD_CHANNEL === 'agent-preview';

export const FEATURES = {
    // Master switch for unfinished or internal-only features
    ENABLE_EXPERIMENTAL_FEATURES,

    // Mature features that should stay visible even when developer features are hidden
    ENABLE_INCREMENTAL_TRANSLATION: true,
    ENABLE_AGENT_WORKSHOP: true,
    ENABLE_PROJECT_HISTORY: true,

    // Mature workflow pages
    ENABLE_NEOLOGISM_TRIBUNAL: true,

    // Help Copilot is visible only in the explicit Agent Preview build channel.
    ENABLE_REMIS_COPILOT: IS_AGENT_PREVIEW,

    // Developer-only pages and tools
    ENABLE_DOCS: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_WORKSHOP_GENERATOR: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_EVENT_RENDERER: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_UI_DEBUGGER: ENABLE_EXPERIMENTAL_FEATURES,
};
