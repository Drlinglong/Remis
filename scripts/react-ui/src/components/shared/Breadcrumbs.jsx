import React from 'react';
import { NavLink, useLocation } from 'react-router';
import { Breadcrumbs as MantineBreadcrumbs, Anchor } from '@mantine/core';

const Breadcrumbs = () => {
    const { pathname } = useLocation();
    const segments = pathname.split('/').filter(Boolean);
    const breadcrumbs = segments.map((segment, index) => ({
        pathname: `/${segments.slice(0, index + 1).join('/')}`,
        label: decodeURIComponent(segment)
            .replaceAll('-', ' ')
            .replace(/\b\w/g, (letter) => letter.toUpperCase()),
    }));

    const items = breadcrumbs.map(({ pathname: matchPath, label }, index) => {
        const isLast = index === breadcrumbs.length - 1;
        return isLast ? (
            <span key={matchPath}>{label}</span>
        ) : (
            <Anchor component={NavLink} to={matchPath} key={matchPath}>
                {label}
            </Anchor>
        );
    });

    return (
        <MantineBreadcrumbs style={{ margin: '16px 0' }}>{items}</MantineBreadcrumbs>
    );
};

export default Breadcrumbs;
