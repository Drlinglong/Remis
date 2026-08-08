// scripts/react-ui/src/config/themes.js

/**
 * A centralized configuration for all available themes in the application.
 * This array is used to dynamically generate the theme selection UI.
 *
 * To add a new theme:
 * 1. Add its semantic token block to `src/themes/definitions.css`.
 * 2. Add a new translation key for the theme's display name in the i18n locale files.
 * 3. Add a new object to this array with the theme's details.
 */
export const AVAILABLE_THEMES = [
  {
    id: 'dark',
    nameKey: 'theme_dark', // Corresponds to the key in translation.json
  },
  {
    id: 'victorian',
    nameKey: 'theme_victorian',
  },
  {
    id: 'byzantine',
    nameKey: 'theme_byzantine',
  },
  {
    id: 'scifi',
    nameKey: 'theme_scifi',
  },
  {
    id: 'wwii',
    nameKey: 'theme_wwii',
  },
  {
    id: 'medieval',
    nameKey: 'theme_medieval',
  },
];
