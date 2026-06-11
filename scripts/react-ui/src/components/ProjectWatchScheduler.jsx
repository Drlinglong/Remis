import { useEffect } from 'react';
import projectWatchService from '../services/projectWatchService';

const SCAN_DUE_INTERVAL_MS = 60 * 1000;
export const PROJECT_WATCHES_UPDATED_EVENT = 'project-watches-updated';

const ProjectWatchScheduler = () => {
  useEffect(() => {
    let cancelled = false;

    const scanDue = async () => {
      try {
        if (!cancelled) {
          const response = await projectWatchService.scanDueWatches();
          const results = Array.isArray(response?.data) ? response.data : [];
          if (results.length > 0) {
            window.dispatchEvent(new CustomEvent(PROJECT_WATCHES_UPDATED_EVENT));
          }
        }
      } catch (error) {
        console.warn('Project watch scheduled scan failed:', error);
      }
    };

    const timer = window.setInterval(scanDue, SCAN_DUE_INTERVAL_MS);
    scanDue();

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return null;
};

export default ProjectWatchScheduler;
