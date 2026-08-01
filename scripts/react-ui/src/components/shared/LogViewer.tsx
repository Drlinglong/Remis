import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../../utils/localizedDateTime';
import { Card, Text } from '@mantine/core';
import './LogViewer.css';
import layoutStyles from '../layout/Layout.module.css';

const LogViewer = ({ logs }) => {
  const { t, i18n } = useTranslation();
  const logContainerRef = useRef(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogColor = (level) => {
    switch (level) {
      case 'INFO':
        return 'white';
      case 'WARN':
        return 'yellow';
      case 'ERROR':
        return 'red';
      default:
        return 'white';
    }
  };

  const formatTimestamp = (date) => {
    return formatLocalizedDateTime(date, getResolvedInterfaceLocale(i18n), { timeStyle: 'medium' });
  };

  return (
    <Card withBorder radius="md" className={layoutStyles.glassCard}>
      <Card.Section withBorder inheritPadding py="xs">
        <Text fw={500}>{t('log_viewer_title')}</Text>
      </Card.Section>
      <div className="log-container" ref={logContainerRef} style={{ paddingTop: "10px" }}>
        {logs.map((log, index) => (
          <div key={index} className="log-entry">
            <Text c={getLogColor(log.level)} style={{ marginRight: '8px' }}>
              [{formatTimestamp(Date.now())}] [{log.level}]
            </Text>
            <Text c="white">{log.message}</Text>
          </div>
        ))}
      </div>
    </Card>
  );
};

export default LogViewer;
