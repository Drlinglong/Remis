import { Children, cloneElement, isValidElement, useLayoutEffect, useRef, useState } from 'react';
import { Tooltip } from '@mantine/core';

import './OverflowAwareLabel.css';

const hasOverflow = (element) => (
    element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight
);

/**
 * Gives a single interactive control an ellipsized label and exposes its full
 * text in a tooltip only when that label is visually clipped.
 */
export function OverflowAwareLabel({ children, description, label, tooltipProps = {} }) {
    const labelRef = useRef(null);
    const [isOverflowing, setIsOverflowing] = useState(false);

    useLayoutEffect(() => {
        const element = labelRef.current;
        if (!element) return undefined;

        const updateOverflow = () => setIsOverflowing(hasOverflow(element));
        updateOverflow();

        const observer = typeof ResizeObserver === 'undefined'
            ? null
            : new ResizeObserver(updateOverflow);
        observer?.observe(element);
        window.addEventListener('resize', updateOverflow);

        return () => {
            observer?.disconnect();
            window.removeEventListener('resize', updateOverflow);
        };
    }, [label]);

    if (!isValidElement(children)) return children;

    const control = cloneElement(Children.only(children), {
        'aria-label': children.props['aria-label'] || label,
        'aria-description': children.props['aria-description'] || description,
        'data-overflowing': isOverflowing || undefined,
        children: <span className="overflow-aware-label" ref={labelRef}>{label}</span>,
    });
    const tooltipTarget = children.props.disabled
        ? <span className="overflow-aware-control">{control}</span>
        : control;
    const tooltipLabel = description
        ? (
            <>
                {isOverflowing && <><strong>{label}</strong><br /></>}
                {description}
            </>
        )
        : label;

    return (
        <Tooltip
            disabled={!isOverflowing && !description}
            label={tooltipLabel}
            withArrow
            {...tooltipProps}
        >
            {tooltipTarget}
        </Tooltip>
    );
}
