import React, { createContext, useState, useContext } from 'react';

const SidebarContext = createContext();

export const SidebarProvider = ({ children }) => {
    const [sidebarContent, setSidebarContent] = useState(null);
    const [sidebarWidth, setSidebarWidth] = useState(300);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

    return (
        <SidebarContext.Provider value={{
            sidebarContent,
            setSidebarContent,
            sidebarWidth,
            setSidebarWidth,
            sidebarCollapsed,
            setSidebarCollapsed
        }}>
            {children}
        </SidebarContext.Provider>
    );
};

export const useSidebar = () => useContext(SidebarContext);
