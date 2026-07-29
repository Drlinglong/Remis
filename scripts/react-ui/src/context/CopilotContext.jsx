import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useLocation } from 'react-router';

/* eslint-disable react-refresh/only-export-components -- provider and its hook form one context API */

const CopilotContext = createContext(null);

const ROUTE_CONTEXTS = [
  { pattern: /^\/$/, pageId: 'home', pageName: '主页 / Home', helpSkillId: 'getting_started' },
  { pattern: /^\/project-management(?:\/[^/]+)?$/, pageId: 'project-management', pageName: '项目管理 / Project Management', helpSkillId: 'getting_started' },
  { pattern: /^\/project-tracking$/, pageId: 'project-tracking', pageName: '项目追踪 / Project Tracking', helpSkillId: 'project_tracking' },
  { pattern: /^\/translation$/, pageId: 'initial-translation', pageName: '初次翻译 / Initial Translation', helpSkillId: 'getting_started' },
  { pattern: /^\/incremental-translation$/, pageId: 'incremental-translation', pageName: '增量翻译 / Incremental Translation', helpSkillId: 'incremental_translation' },
  { pattern: /^\/proofreading$/, pageId: 'proofreading', pageName: '校对 / Proofreading', helpSkillId: 'proofreading' },
  { pattern: /^\/agent-workshop$/, pageId: 'agent-workshop', pageName: '格式修复台 / Format Repair', helpSkillId: 'agent_workshop' },
  { pattern: /^\/glossary-manager$/, pageId: 'glossary-manager', pageName: '词典管理 / Glossary Manager', helpSkillId: 'glossary' },
  { pattern: /^\/neologism-review$/, pageId: 'neologism-review', pageName: '术语法庭 / Neologism Tribunal', helpSkillId: 'neologism_tribunal' },
  { pattern: /^\/archives$/, pageId: 'archives', pageName: '归档 / Archives', helpSkillId: 'project_tracking' },
  { pattern: /^\/settings$/, pageId: 'settings', pageName: '设置 / Settings', helpSkillId: 'settings' },
  { pattern: /^\/tools$/, pageId: 'tools', pageName: '工具箱 / Tools', helpSkillId: 'thumbnail_generator' },
  { pattern: /^\/docs$/, pageId: 'documentation', pageName: '使用文档 / Documentation', helpSkillId: 'faq' },
  { pattern: /^\/copilot$/, pageId: 'copilot', pageName: 'Remis 小助手 / Copilot', helpSkillId: 'faq' },
];

export function resolveCopilotRouteContext(pathname) {
  const normalizedPath = pathname || '/';
  const match = ROUTE_CONTEXTS.find((item) => item.pattern.test(normalizedPath));
  if (!match) {
    return {
      pageId: 'unknown',
      pageName: '未知页面 / Unknown Page',
      path: normalizedPath,
      contextSource: 'router',
    };
  }
  return {
    pageId: match.pageId,
    pageName: match.pageName,
    helpSkillId: match.helpSkillId,
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
