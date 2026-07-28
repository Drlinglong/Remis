import { useCallback } from 'react';
import { useNavigate } from 'react-router';
import api from '../utils/api';
import { fetchCopilotActionDetail } from '../services/copilotService';

/**
 * Execute a Phase-1 whitelist action on the client.
 * Navigation / open logs / open URL only — no write operations yet.
 */
export function useCopilotActions() {
  const navigate = useNavigate();

  const runAction = useCallback(
    async (actionId, args = {}) => {
      if (!actionId || actionId === 'none') {
        return { ok: true, skipped: true };
      }

      let detail;
      try {
        detail = await fetchCopilotActionDetail(actionId);
      } catch (err) {
        // Fallback map if detail endpoint fails
        const fallback = FALLBACK_ACTIONS[actionId];
        if (!fallback) {
          throw err;
        }
        detail = fallback;
      }

      const kind = detail.client_kind;
      if (kind === 'navigate' && detail.path) {
        navigate(detail.path, { state: { copilotArgs: args, hashHint: detail.hash_hint } });
        return { ok: true, kind };
      }

      if (kind === 'api_post' && detail.endpoint) {
        await api.post(detail.endpoint, args || {});
        return { ok: true, kind };
      }

      if (kind === 'open_url' && detail.url) {
        try {
          await api.post('/api/system/open-url', { url: detail.url });
        } catch {
          window.open(detail.url, '_blank', 'noopener,noreferrer');
        }
        return { ok: true, kind };
      }

      return { ok: false, reason: 'unsupported_action' };
    },
    [navigate],
  );

  return { runAction };
}

const FALLBACK_ACTIONS = {
  open_api_settings: { client_kind: 'navigate', path: '/settings', hash_hint: 'api' },
  open_provider_docs: { client_kind: 'navigate', path: '/settings' },
  open_project_management: { client_kind: 'navigate', path: '/project-management' },
  open_create_project: { client_kind: 'navigate', path: '/project-management' },
  open_initial_translation: { client_kind: 'navigate', path: '/translation' },
  open_proofreading: { client_kind: 'navigate', path: '/proofreading' },
  open_agent_workshop: { client_kind: 'navigate', path: '/agent-workshop' },
  open_glossary_manager: { client_kind: 'navigate', path: '/glossary-manager' },
  open_deploy_dialog: { client_kind: 'navigate', path: '/project-management' },
  open_log_folder: { client_kind: 'api_post', endpoint: '/api/system/open-logs' },
  open_github_issues: {
    client_kind: 'open_url',
    url: 'https://github.com/Drlinglong/Remis/issues',
  },
  open_github_issue_132: {
    client_kind: 'open_url',
    url: 'https://github.com/Drlinglong/Remis/issues/132',
  },
};
