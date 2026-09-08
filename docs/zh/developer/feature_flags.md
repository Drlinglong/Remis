# Feature Flags Guide

To facilitate development and release management, we use a **Feature Flag** system to control the visibility of experimental or incomplete features.

## Master Switch configuration

Configuration file location: `scripts/react-ui/src/config/features.js`

We provide a **Master Switch** (`ENABLE_EXPERIMENTAL_FEATURES`) to toggle all features marked as "Experimental" or "WIP" at once.

## Release channels

Release identity is defined by `scripts/build_profile.py` and selected through
`REMIS_BUILD_CHANNEL`. The stable channel is the 3.2.0 production build; the
`agent-preview` channel uses version `3.2.0-agent-preview.1`, port 1454, and an
isolated data directory. Both released channels enable the Agent/Copilot,
Project Archive, and checkpoint/resume workflows. Unknown channels fail closed
for the archive and checkpoint/resume gates.

The backend and frontend must use the same channel decision. When changing a
release gate, update `scripts/core/feature_policy.py`,
`scripts/react-ui/src/config/features.js`, and their focused tests together.

### How to use

- **Enable Experimental Features** (Development Mode):
  Set `ENABLE_EXPERIMENTAL_FEATURES` to `true`.
  
  ```javascript
  const ENABLE_EXPERIMENTAL_FEATURES = true;
  ```
  
  *Effect*: Displays "Neologism Miner", "Documentation", and hidden "Tools" (Workshop Generator, Event Renderer, UI Debugger).

- **Disable Experimental Features** (Release Mode):
  Set `ENABLE_EXPERIMENTAL_FEATURES` to `false`.
  
  ```javascript
  const ENABLE_EXPERIMENTAL_FEATURES = false;
  ```
  
  *Effect*: Hides all the above unfinished modules, keeping the interface clean for end users.

## Adding new Feature Flags

When adding a new unfinished feature, please follow these steps:

1. Define the flag in the `FEATURES` object in `scripts/react-ui/src/config/features.js`.
2. Initialize it with the value of `ENABLE_EXPERIMENTAL_FEATURES`.

```javascript
export const FEATURES = {
    // ...
    ENABLE_MY_NEW_FEATURE: ENABLE_EXPERIMENTAL_FEATURES,
};
```

3. Call `FEATURES.ENABLE_MY_NEW_FEATURE` in the frontend code to conditionally render the component or route.
