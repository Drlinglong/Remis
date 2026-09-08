import React, { useId } from 'react';
import { Text } from '@mantine/core';

import styles from './PublishedContextWorkbench.module.css';

const parseSections = (summary = '') => String(summary)
    .trim()
    .split(/\n{2,}/)
    .map((block) => {
        const [heading, ...body] = block.split('\n');
        return body.length > 0
            ? { heading: heading.trim(), body: body.join('\n').trim() }
            : { heading: '', body: heading.trim() };
    })
    .filter((section) => section.body);

const PublishedContextProjectSummary = ({ summary, t }) => {
    const headingId = useId();
    const sections = parseSections(summary);
    if (sections.length === 0) return null;

    return (
        <section
            className={styles.summaryPanel}
            data-testid="published-context-project-summary"
            data-remis-surface="surface"
            aria-labelledby={headingId}
        >
            <Text
                className={styles.summaryPanelLabel}
                component="h2"
                id={headingId}
            >
                {t('mod_archive.tree_v2.summary', { defaultValue: 'Archive overview' })}
            </Text>
            <div className={styles.summaryGrid} data-section-count={sections.length}>
                {sections.map((section, index) => (
                    <article
                        className={styles.summarySection}
                        data-primary={index === 0 ? 'true' : 'false'}
                        data-section-index={index}
                        key={`${section.heading}-${index}`}
                    >
                        {section.heading && (
                            <Text className={styles.summaryHeading} component="h3">
                                {section.heading}
                            </Text>
                        )}
                        <Text className={styles.projectSummary} size="sm">{section.body}</Text>
                    </article>
                ))}
            </div>
        </section>
    );
};

export default PublishedContextProjectSummary;
