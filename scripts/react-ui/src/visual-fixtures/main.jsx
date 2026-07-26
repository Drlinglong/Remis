import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider } from '@mantine/core';

import '@mantine/core/styles.css';
import '../index.css';
import '../themes/index.css';
import '../themes/definitions.css';
import { theme as customTheme } from '../theme';
import VisualReliabilityLab from './VisualReliabilityLab';

const supportedThemes = new Set(['victorian', 'byzantine', 'scifi', 'wwii', 'medieval']);
const requestedTheme = new URLSearchParams(window.location.search).get('theme');
const activeTheme = supportedThemes.has(requestedTheme) ? requestedTheme : 'scifi';
const rootElement = window.document.documentElement;

rootElement.setAttribute('data-theme', activeTheme);
rootElement.classList.remove('victorian', 'byzantine', 'scifi', 'wwii', 'medieval');
rootElement.classList.add(activeTheme);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider theme={customTheme} defaultColorScheme="dark">
      <VisualReliabilityLab themeId={activeTheme} />
    </MantineProvider>
  </StrictMode>,
);
