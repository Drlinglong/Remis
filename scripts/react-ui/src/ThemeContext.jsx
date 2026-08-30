import React, { createContext, useState, useEffect, useMemo } from 'react';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import '@mantine/notifications/styles.css';
import { theme as customTheme } from './theme';

// 1. Create the context
const ThemeContext = createContext();

// 2. Create the provider component
export const ThemeProvider = ({ children }) => {
  // State to hold the current theme
  const [theme, setTheme] = useState(() => {
    // Default to 'scifi' if no theme is saved, or if saved is 'dark' (legacy)
    const savedTheme = localStorage.getItem('theme');
    if (!savedTheme || savedTheme === 'dark') return 'scifi';
    return savedTheme;
  });

  // Effect to apply the theme data attribute to the html element
  useEffect(() => {
    const root = window.document.documentElement;
    root.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  // The function to change the theme
  const toggleTheme = (newTheme) => {
    if (newTheme) {
      setTheme(newTheme);
    }
  };

  const value = useMemo(() => ({
    theme,
    toggleTheme,
  }), [theme]);

  return (
    <ThemeContext.Provider value={value}>
      <MantineProvider theme={customTheme} defaultColorScheme="dark">
        <Notifications
          position="top-center"
          autoClose={3200}
          limit={3}
          zIndex={10000}
        />
        {children}
      </MantineProvider>
    </ThemeContext.Provider>
  );
};

export default ThemeContext;
