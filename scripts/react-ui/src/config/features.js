/**
 * Feature Flags configuration
 * Used to toggle features on/off for different builds/releases.
 */
// MASTER SWITCH
const ENABLE_EXPERIMENTAL_FEATURES = false; // Toggle this to show/hide all WIP features

export const FEATURES = {
    // Export master switch status if needed for UI indications
    ENABLE_EXPERIMENTAL_FEATURES,

    // Neologism Tribunal (新词审判庭)
    ENABLE_NEOLOGISM_TRIBUNAL: ENABLE_EXPERIMENTAL_FEATURES,

    // Documentation
    ENABLE_DOCS: ENABLE_EXPERIMENTAL_FEATURES,

    // Tools Tab Features
    ENABLE_WORKSHOP_GENERATOR: ENABLE_EXPERIMENTAL_FEATURES, // Steam Workshop Description Generator
    ENABLE_EVENT_RENDERER: ENABLE_EXPERIMENTAL_FEATURES,     // Paradox Event Renderer
    ENABLE_UI_DEBUGGER: ENABLE_EXPERIMENTAL_FEATURES,        // Internal UI Debugger

    // Providers
    ENABLE_HUNYUAN_PROVIDER: ENABLE_EXPERIMENTAL_FEATURES    // Hunyuan (Tencent) Provider
};
