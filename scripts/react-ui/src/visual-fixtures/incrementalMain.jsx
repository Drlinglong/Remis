import React from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider } from '@mantine/core';

import '@mantine/core/styles.css';
import '../index.css';
import '../themes/index.css';
import '../themes/definitions.css';
import '../i18n/i18n';
import { theme as customTheme } from '../theme';
import IncrementalTranslationVisualLab from './IncrementalTranslationVisualLab';

const supportedThemes = new Set(['victorian', 'byzantine', 'scifi', 'wwii', 'medieval']);
const params = new URLSearchParams(window.location.search);
const requestedTheme = params.get('theme');
const activeTheme = supportedThemes.has(requestedTheme) ? requestedTheme : 'scifi';
const activeStep = ['project', 'config', 'prescan', 'execution'].includes(params.get('step'))
  ? params.get('step')
  : 'project';
const rootElement = window.document.documentElement;

rootElement.setAttribute('data-theme', activeTheme);
rootElement.classList.remove('victorian', 'byzantine', 'scifi', 'wwii', 'medieval');
rootElement.classList.add(activeTheme);

createRoot(document.getElementById('root')).render(
  <MantineProvider theme={customTheme} defaultColorScheme="dark">
    <IncrementalTranslationVisualLab step={activeStep} themeId={activeTheme} />
  </MantineProvider>,
);
