import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router-dom';
import ProjectValidation from './ProjectValidation';
import api from '../../utils/api';

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn() },
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, options) => options?.defaultValue || key }),
}));

const Target = () => {
  const location = useLocation();
  return <div data-testid="target-location">{location.pathname}{location.search}</div>;
};

describe('ProjectValidation', () => {
  it('opens an individual validation issue at its stable proofreading entry key', async () => {
    api.get.mockResolvedValue({
      data: {
        issues_count: 1,
        issue_type_counts: { validation_example: 1 },
        issues: [{
          file_id: 'file-1',
          file_name: 'localization/demo.yml',
          key: 'demo.key:0',
          line_number: 42,
          error_code: 'validation_example',
        }],
        sidecar_candidates: [],
      },
    });
    const router = createMemoryRouter([
      { path: '/project', element: <ProjectValidation projectId="project-1" /> },
      { path: '/proofreading', element: <Target /> },
    ], { initialEntries: ['/project'] });

    render(<MantineProvider><RouterProvider router={router} /></MantineProvider>);
    const button = await screen.findByRole('button', { name: 'Manual proofreading' });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('target-location')).toHaveTextContent(
        '/proofreading?projectId=project-1&fileId=file-1&entryKey=demo.key%3A0&lineHint=42'
      );
    });
  });
});
