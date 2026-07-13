import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

/* eslint-disable react-refresh/only-export-components -- provider and its hook form one context API */

const CopilotContext = createContext(null);

export function CopilotContextProvider({ children }) {
  const [pageContext, setPageContext] = useState(null);

  const registerPageContext = useCallback((context) => {
    setPageContext(context ? { ...context, capturedAt: new Date().toISOString() } : null);
  }, []);

  const value = useMemo(() => ({ pageContext, registerPageContext }), [pageContext, registerPageContext]);
  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}

export function useRemisCopilotContext() {
  const value = useContext(CopilotContext);
  if (!value) throw new Error('useRemisCopilotContext must be used inside CopilotContextProvider');
  return value;
}
