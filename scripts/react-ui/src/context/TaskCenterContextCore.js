import { createContext, useContext } from 'react';

export const TaskCenterContext = createContext(null);

export const useTaskCenter = () => {
  const context = useContext(TaskCenterContext);
  if (!context) {
    throw new Error('useTaskCenter must be used within TaskCenterProvider');
  }
  return context;
};
