import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CopilotPage from './CopilotPage';
import { fetchCopilotStatus } from '../services/copilotService';

vi.mock('../services/copilotService', () => ({ fetchCopilotStatus: vi.fn() }));
vi.mock('../components/copilot/RemisCopilotThread', () => ({ default: () => <div>thread</div> }));
vi.mock('../components/copilot/CopilotSessionSidebar', () => ({ default: () => <div>sessions</div> }));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_key, fallback) => fallback || _key, i18n: { language: 'zh' } }),
}));

describe('CopilotPage shared model status', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchCopilotStatus.mockResolvedValue({
      default_provider: 'openai',
      default_model: 'gpt-5.6-luna',
      reasoning_enabled: true,
      reasoning_preset: 'high',
      context_budget_tokens: 200000,
    });
  });

  it('shows the effective provider, model and reasoning strength', async () => {
    render(<MantineProvider><CopilotPage /></MantineProvider>);

    expect(await screen.findByText(/供应商: openai/)).toBeInTheDocument();
    expect(screen.getByText(/模型: gpt-5.6-luna/)).toBeInTheDocument();
    expect(screen.getByText(/推理: high/)).toBeInTheDocument();
    expect(screen.queryByText('模型选择器：后续版本')).not.toBeInTheDocument();
    expect(screen.getByText('Agent Preview')).toBeInTheDocument();
  });
});
