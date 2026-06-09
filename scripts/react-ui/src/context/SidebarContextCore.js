import { createContext, useContext } from 'react';

export const SidebarContext = createContext();

export const useSidebar = () => useContext(SidebarContext);
