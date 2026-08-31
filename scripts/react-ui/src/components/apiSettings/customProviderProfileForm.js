export const isValidProviderBaseUrl = (value) => {
    try {
        const parsed = new URL(value.trim());
        const path = parsed.pathname.toLowerCase().replace(/\/$/, '');
        return ['http:', 'https:'].includes(parsed.protocol)
            && Boolean(parsed.hostname)
            && !parsed.username
            && !parsed.password
            && !parsed.search
            && !parsed.hash
            && !path.endsWith('/chat/completions')
            && !path.endsWith('/responses');
    } catch {
        return false;
    }
};
