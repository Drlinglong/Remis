const DEFAULT_EXPANSION = 0.4;

/** Expand UI copy deterministically so layout tests catch long-locale clipping. */
export const expandPseudoLocale = (text, expansion = DEFAULT_EXPANSION) => {
    const characters = Array.from(String(text));
    if (characters.length === 0) return '';

    const targetLength = Math.ceil(characters.length * (1 + expansion));
    const paddingLength = Math.max(0, targetLength - characters.length - 2);
    return `［${characters.join('')}${'·'.repeat(paddingLength)}］`;
};
