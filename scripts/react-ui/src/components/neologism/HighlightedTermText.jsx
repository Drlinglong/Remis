import React from 'react';
import { Text } from '@mantine/core';

import styles from './JudgmentCourt.module.css';

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const HighlightedTermText = ({ term, text }) => {
    if (!text || !term) return <Text>{text}</Text>;
    const parts = text.split(new RegExp(`(${escapeRegExp(term)})`, 'gi'));

    return (
        <Text size="sm" c="dimmed" lh={1.6} className={styles.highlightedText}>
            {parts.map((part, index) => (
                part.toLowerCase() === term.toLowerCase()
                    ? <mark className={styles.termMark} key={`${part}:${index}`}>{part}</mark>
                    : part
            ))}
        </Text>
    );
};

export default HighlightedTermText;
