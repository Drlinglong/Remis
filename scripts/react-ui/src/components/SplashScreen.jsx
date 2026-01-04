import React, { useState, useEffect, useContext } from 'react';
import { Center, Stack, Title, Text, Button, Transition, Box, RingProgress, ThemeIcon, Group, Select } from '@mantine/core';
import { IconRocket, IconCheck, IconServer2, IconDatabase, IconPlugConnected, IconWorld } from '@tabler/icons-react';
import api from '../utils/api';
import { useTranslation } from 'react-i18next';
import ThemeContext from '../ThemeContext';

const SplashScreen = ({ onReady }) => {
    const { t, i18n } = useTranslation();
    const { theme } = useContext(ThemeContext);
    const [status, setStatus] = useState('connecting'); // connecting, ready, error
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState([]);

    // Poll backend
    useEffect(() => {
        let isMounted = true;
        const addLog = (msg) => setLogs(prev => [...prev.slice(-4), msg]);

        // Minimum loading time (1s) to prevent "glitchy" fast transitions
        const MIN_LOADING_TIME = 1000;
        const mountTime = Date.now();

        const checkHealth = async () => {
            try {
                addLog('Pinging Neural Link (API)...');
                const start = Date.now();
                // We ping the health endpoint with silent: true to avoid console log flooding on failure
                await api.get('/api/health', { silent: true });

                if (!isMounted) return;

                const latency = Date.now() - start;
                addLog(`Connection established. Latency: ${latency}ms`);

                // Enforce minimum splash duration
                const elapsedSinceMount = Date.now() - mountTime;
                if (elapsedSinceMount < MIN_LOADING_TIME) {
                    const remaining = MIN_LOADING_TIME - elapsedSinceMount;
                    addLog(`Calibrating systems... (${remaining}ms)`);
                    await new Promise(resolve => setTimeout(resolve, remaining));
                }

                if (!isMounted) return;

                setProgress(100);
                setStatus('ready');

            } catch (error) {
                if (!isMounted) return;
                addLog(`Connection failed... retrying in 500ms`);
                // Retry in 500ms
                setTimeout(checkHealth, 500);
            }
        };

        // Smooth progress animation
        const interval = setInterval(() => {
            setProgress(p => {
                // Asymptotic approach to 90%
                if (p >= 90) return p;
                // Move 1% closer to 90% each frame
                const remaining = 90 - p;
                return p + (remaining * 0.05) + 0.1;
            });
        }, 30);

        // Start checking
        checkHealth();

        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    // Theme Configuration
    const getThemeStyles = (themeName) => {
        const configs = {
            scifi: {
                overlay: 'rgba(5, 5, 8, 0.7)', // Darker, lets the stars shine through slightly
                textColor: 'white',
                dimmedColor: 'rgba(255,255,255,0.6)',
                accent: 'cyan',
                ringColor: 'blue',
                font: 'Roboto, sans-serif'
            },
            victorian: {
                overlay: 'rgba(30, 20, 10, 0.85)', // Dark brown wood tint
                textColor: '#e6ccb2',
                dimmedColor: 'rgba(230, 204, 178, 0.6)',
                accent: 'orange', // Brass-like
                ringColor: 'orange',
                font: 'Playfair Display, serif'
            },
            byzantine: {
                overlay: 'rgba(20, 10, 30, 0.85)', // Deep Purple tint
                textColor: '#FFD700', // Gold
                dimmedColor: 'rgba(255, 215, 0, 0.6)',
                accent: 'yellow',
                ringColor: 'grape',
                font: 'Cinzel, serif'
            },
            wwii: {
                overlay: 'rgba(40, 45, 30, 0.85)', // Olive Drab tint
                textColor: '#f0f0f0',
                dimmedColor: 'rgba(240, 240, 240, 0.6)',
                accent: 'lime',
                ringColor: 'green',
                font: 'Courier Prime, monospace' // Typewriter style
            },
            medieval: {
                overlay: 'rgba(10, 5, 5, 0.8)',
                textColor: '#f0e6d2', // Parchment
                dimmedColor: 'rgba(240, 230, 210, 0.6)',
                accent: 'red',
                ringColor: 'red',
                font: 'MedievalSharp, serif' // If available, otherwise serif
            }
        };
        return configs[themeName] || configs.scifi;
    };

    const styles = getThemeStyles(theme);

    return (
        <Box style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            // We use a semi-transparent background to let the GlobalStyles texture show through,
            // but dark enough to ensure text readability.
            background: styles.overlay,
            color: styles.textColor,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            fontFamily: styles.font,
            transition: 'background 0.5s ease, color 0.5s ease'
        }}>

            {/* Main Content Stack */}
            <Stack align="center" style={{ zIndex: 1, position: 'relative', maxWidth: '400px', width: '90%' }}>

                {/* Language Selector - Prominent */}
                <Box style={{ position: 'absolute', top: -100, right: 0, opacity: 0.8, transition: 'opacity 0.2s' }} className="lang-selector-container">
                    {/* Moved into main stack for visibility or keep absolute? 
                         User said "Obvious dropdown". Let's put it clearly above the progress ring.
                     */}
                </Box>

                <Stack gap={4} mb="xl" align="center">
                    <Text size="xs" fw={700} style={{ letterSpacing: '2px', textTransform: 'uppercase', color: styles.dimmedColor, opacity: 0.8 }}>
                        {t('splash_language_menu', 'LANGUAGE MENU')}
                    </Text>
                    <Select
                        leftSection={<IconWorld size={16} />}
                        placeholder="Language"
                        data={[
                            { value: 'en', label: 'English (en-US)' },
                            { value: 'zh', label: '简体中文 (zh-CN)' }
                        ]}
                        value={i18n.language ? i18n.language.split('-')[0] : 'en'}
                        onChange={(val) => {
                            if (val) i18n.changeLanguage(val);
                        }}
                        comboboxProps={{ zIndex: 10005 }}
                        styles={{
                            input: {
                                backgroundColor: 'rgba(20, 20, 20, 0.6)',
                                color: styles.textColor,
                                borderColor: styles.dimmedColor,
                                textAlign: 'center',
                                backdropFilter: 'blur(5px)'
                            },
                            dropdown: {
                                backgroundColor: '#1A1B1E',
                                color: '#C1C2C5',
                                border: `1px solid ${styles.dimmedColor}`,
                                boxShadow: '0 4px 20px rgba(0,0,0,0.5)'
                            },
                            option: {
                                color: '#C1C2C5'
                            }
                        }}
                        w={200}
                        variant="filled"
                        radius="md"
                        allowDeselect={false}
                        checkIconPosition="right"
                    />
                </Stack>

                <img
                    src="/Project Remis.png"
                    alt="Remis Logo"
                    style={{
                        height: '100px',
                        marginBottom: '20px',
                        filter: 'drop-shadow(0 0 15px rgba(0,0,0,0.5))',
                        objectFit: 'contain'
                    }}
                />

                <RingProgress
                    size={240}
                    thickness={6}
                    roundCaps
                    sections={[{ value: progress, color: status === 'ready' ? 'teal' : styles.ringColor }]}
                    label={
                        <Center>
                            {status === 'ready' ? (
                                <ThemeIcon color="teal" variant="light" radius="xl" size={60}>
                                    <IconCheck size={40} />
                                </ThemeIcon>
                            ) : (
                                <Text fw={700} size="xl" ta="center" c={styles.textColor}>
                                    {Math.round(progress)}%
                                </Text>
                            )}
                        </Center>
                    }
                />

                <Stack align="center" gap={4}>
                    <Title order={1} style={{ letterSpacing: '2px', fontWeight: 900, color: styles.textColor }}>
                        REMIS
                    </Title>
                    <Text size="sm" style={{ letterSpacing: '4px', textTransform: 'uppercase', color: styles.dimmedColor }}>
                        Localization Factory
                    </Text>
                </Stack>

                <Box h={60} w="100%" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    {status === 'connecting' && (
                        <Text size="xs" className="fade-in" style={{ color: styles.dimmedColor }}>
                            {logs[logs.length - 1] || "Initializing..."}
                        </Text>
                    )}

                    {status === 'ready' && (
                        <Transition mounted={status === 'ready'} transition="pop" duration={400} timingFunction="ease">
                            {(transitionStyles) => (
                                <Button
                                    style={{ ...transitionStyles, boxShadow: `0 0 20px ${styles.accent}` }}
                                    size="lg"
                                    color={styles.accent}
                                    variant={theme === 'scifi' ? 'gradient' : 'filled'}
                                    gradient={theme === 'scifi' ? { from: 'blue', to: 'cyan' } : undefined}
                                    onClick={onReady}
                                    className="pulse-button"
                                    leftSection={<IconRocket />}
                                    fullWidth
                                >
                                    {t('enter_system', 'ENTER SYSTEM')}
                                </Button>
                            )}
                        </Transition>
                    )}
                </Box>

                <Group gap="xl" mt="xl" style={{ opacity: 0.5 }}>
                    <Group gap="xs">
                        <IconServer2 size={16} color={styles.textColor} />
                        <Text size="xs" c={styles.textColor}>Backend</Text>
                    </Group>
                    <Group gap="xs">
                        <IconDatabase size={16} color={styles.textColor} />
                        <Text size="xs" c={styles.textColor}>Database</Text>
                    </Group>
                    <Group gap="xs">
                        <IconPlugConnected size={16} color={styles.textColor} />
                        <Text size="xs" c={styles.textColor}>API</Text>
                    </Group>
                </Group>
            </Stack>
        </Box>
    );
};

export default SplashScreen;
