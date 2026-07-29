import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';

import {
  CopilotContextProvider,
  resolveCopilotRouteContext,
  useRemisCopilotContext,
} from './CopilotContext';

function ContextProbe() {
  const { pageContext } = useRemisCopilotContext();
  return <pre>{JSON.stringify(pageContext)}</pre>;
}

describe('CopilotContext', () => {
  it('resolves project tracking to its help skill', () => {
    expect(resolveCopilotRouteContext('/project-tracking')).toEqual(expect.objectContaining({
      pageId: 'project-tracking',
      pageName: '项目追踪 / Project Tracking',
      helpSkillId: 'project_tracking',
    }));
  });

  it('recognizes project management detail routes', () => {
    expect(resolveCopilotRouteContext('/project-management/project-1').pageId).toBe('project-management');
  });

  it('names the user tool Format Repair without renaming the internal Remis Agent', () => {
    const context = resolveCopilotRouteContext('/agent-workshop');

    expect(context).toEqual(expect.objectContaining({
      pageId: 'agent-workshop',
      pageName: '格式修复台 / Format Repair',
      helpSkillId: 'agent_workshop',
    }));
    expect(context.pageName).not.toContain('Remis Agent');
  });

  it('always supplies route context to the floating assistant', () => {
    render(
      <MemoryRouter initialEntries={['/project-tracking']}>
        <CopilotContextProvider>
          <ContextProbe />
        </CopilotContextProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/project-tracking/)).toHaveTextContent('project_tracking');
  });
});
