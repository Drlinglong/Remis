import React, { useState, useEffect } from 'react';
import { NotificationContext } from './NotificationContextCore';

export const NotificationProvider = ({ children }) => {
  const [notificationStyle, setNotificationStyle] = useState(
    () => localStorage.getItem('notificationStyle') || 'minimal'
  );

  useEffect(() => {
    localStorage.setItem('notificationStyle', notificationStyle);
  }, [notificationStyle]);

  const value = {
    notificationStyle,
    setNotificationStyle,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};
