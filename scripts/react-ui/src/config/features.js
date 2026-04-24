/**
 * Developer feature master switch.
 * Keep this false for normal user-facing builds.
 */
const ENABLE_EXPERIMENTAL_FEATURES = false;

export const FEATURES = {
    // Master switch for unfinished or internal-only features
    ENABLE_EXPERIMENTAL_FEATURES,

    // Mature features that should stay visible even when developer features are hidden
    ENABLE_INCREMENTAL_TRANSLATION: true,
    ENABLE_AGENT_WORKSHOP: true,
    ENABLE_PROJECT_HISTORY: true,

    // Developer-only pages and tools
    ENABLE_NEOLOGISM_TRIBUNAL: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_DOCS: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_WORKSHOP_GENERATOR: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_EVENT_RENDERER: ENABLE_EXPERIMENTAL_FEATURES,
    ENABLE_UI_DEBUGGER: ENABLE_EXPERIMENTAL_FEATURES,

    // Developer-only providers
    ENABLE_HUNYUAN_PROVIDER: ENABLE_EXPERIMENTAL_FEATURES,
};
