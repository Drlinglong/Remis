import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useLocation } from 'react-router';
import { resolveRegisteredPage } from '../config/pageRegistry';

/* eslint-disable react-refresh/only-export-components -- provider and its hook form one context API */

const CopilotContext = createContext(null);

export function resolveCopilotRouteContext(pathname) {
  const normalizedPath = pathname || '/';
  const page = resolveRegisteredPage(normalizedPath);
  if (!page?.copilot) {
    return {
      pageId: 'unknown',
      pageName: '未知页面 / Unknown Page',
      path: normalizedPath,
      contextSource: 'router',
    };
  }
  return {
    pageId: page.id,
    pageName: page.copilot.pageName,
    helpSkillId: page.copilot.helpSkillId,
    path: normalizedPath,
    contextSource: 'router',
  };
}

export function CopilotContextProvider({ children }) {
  const location = useLocation();
  const [registeredContext, setRegisteredContext] = useState(null);
  const routeContext = useMemo(
    () => ({ ...resolveCopilotRouteContext(location.pathname), capturedAt: new Date().toISOString() }),
    [location.pathname],
  );

  const registerPageContext = useCallback((context) => {
    setRegisteredContext(context ? {
      path: location.pathname,
      data: { ...context, capturedAt: new Date().toISOString() },
    } : null);
  }, [location.pathname]);

  const pageContext = useMemo(() => {
    if (registeredContext?.path !== location.pathname) {
      return routeContext;
    }
    return { ...routeContext, ...registeredContext.data, path: location.pathname };
  }, [location.pathname, registeredContext, routeContext]);

  const value = useMemo(() => ({ pageContext, registerPageContext }), [pageContext, registerPageContext]);
  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}

export function useRemisCopilotContext() {
  const value = useContext(CopilotContext);
  if (!value) throw new Error('useRemisCopilotContext must be used inside CopilotContextProvider');
  return value;
}
