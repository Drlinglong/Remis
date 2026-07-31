import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { DescriptionGenerationPanel } from './DescriptionGenerationPanel';

describe('DescriptionGenerationPanel', () => {
  it('requires explicit approval before sending a model request', async () => {
    const onGenerate = vi.fn().mockResolvedValue({ version_id: 'version-1' });
    render(
      <MantineProvider>
        <DescriptionGenerationPanel
          isGenerating={false}
          onGenerate={onGenerate}
          workshopItemId="3538617386"
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: '模型生成' }));
    const confirm = await screen.findByRole('button', { name: '确认生成' });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Model'), {
      target: { value: 'google/gemma-4-31b-qat' },
    });
    fireEvent.click(screen.getByRole('checkbox', {
      name: '我确认执行这次模型调用，并将结果保存为候选版本',
    }));
    expect(confirm).toBeEnabled();

    fireEvent.click(confirm);

    expect(onGenerate).toHaveBeenCalledWith(expect.objectContaining({
      approved: true,
      model: 'google/gemma-4-31b-qat',
      provider: 'lm_studio',
    }));
  });
});
