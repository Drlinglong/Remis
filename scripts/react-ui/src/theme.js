import { createTheme } from '@mantine/core';

export const theme = createTheme({
  colors: {
    // Custom dark palette based on "Google Modern Dark"
    // We map these to Mantine's color system
    dark: [
      '#C1C2C5', // 0: Text
      '#A6A7AB', // 1: Dimmed text
      '#909296', // 2
      '#5C5F66', // 3
      '#373A40', // 4
      '#2C2E33', // 5
      '#2A2A2A', // 6: Surface / Card Background (colorBgContainer)
      '#1F1F1F', // 7: Main Background (colorBgLayout)
      '#141517', // 8
      '#101113', // 9
    ],
    // Primary color: #89B4FA (Light Blue)
    // Generated shades for a complete palette
    brand: [
      '#E7F1FF',
      '#D0E3FF',
      '#A8C9FF',
      '#89B4FA', // Main Primary
      '#6B9EF0',
      '#4D89E6',
      '#3074DC',
      '#125FD2',
      '#004AC8',
      '#0036BE',
    ],
  },
  primaryColor: 'brand',
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif',

  components: {
    Card: {
      defaultProps: {
        bg: 'dark.6',
        withBorder: true,
      },
      styles: (_theme) => ({
        root: {
          borderColor: 'rgba(255, 255, 255, 0.1)',
          boxShadow: 'none',
        },
      }),
    },
    Button: {
      defaultProps: {
        radius: 'md',
      },
    },
    AppShell: {
      styles: (theme) => ({
        main: {
          backgroundColor: theme.colors.dark[7], // #1F1F1F
        },
        navbar: {
          backgroundColor: theme.colors.dark[6], // #2A2A2A
          borderColor: 'rgba(255, 255, 255, 0.1)',
        },
        header: {
          backgroundColor: theme.colors.dark[6], // #2A2A2A
          borderColor: 'rgba(255, 255, 255, 0.1)',
        },
      }),
    },
  },
});
