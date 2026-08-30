import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MantineProvider } from '@mantine/core';
import CustomProviderProfiles from './CustomProviderProfiles';
import api from '../../utils/api';
import { notifications } from '@mantine/notifications';

vi.mock('../../utils/api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
    },
}));

vi.mock('@mantine/notifications', () => ({
    notifications: { show: vi.fn() },
}));

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key) => key }),
}));

const profile = {
    profile_id: 'profile-provider-a',
    display_name: 'Provider A',
    adapter_id: 'your_favourite_api',
    api_url: 'https://provider-a.example/v1',
    selected_model: 'model-a',
    available_models: ['model-a'],
    models: [],
    has_key: true,
    masked_key: 'sk-••••1234',
    reasoning: { supported: false, custom_parameters: {} },
};

const renderProfiles = () => render(
    <MantineProvider>
        <CustomProviderProfiles />
    </MantineProvider>,
);

describe('CustomProviderProfiles', () => {
    afterEach(() => cleanup());

    beforeEach(() => {
        vi.clearAllMocks();
        api.get.mockResolvedValue({ data: [profile] });
        api.post.mockResolvedValue({ data: { profile } });
        api.patch.mockResolvedValue({ data: { profile } });
        api.delete.mockResolvedValue({ data: { status: 'deleted' } });
    });

    it('renders profiles in an independent section and never renders the secret value', async () => {
        renderProfiles();

        expect(await screen.findByText('custom_profiles_title')).toBeInTheDocument();
        expect(screen.getAllByText('Provider A').length).toBeGreaterThan(0);
        expect(screen.getByText('sk-••••1234')).toBeInTheDocument();
        expect(screen.queryByText('secret-value')).not.toBeInTheDocument();
        expect(api.get).toHaveBeenCalledWith('/api/providers/profiles');
    });

    it('creates a profile through the expected POST contract after filling the draft', async () => {
        const created = { ...profile, profile_id: 'profile-provider-b', display_name: 'Provider B' };
        api.post.mockResolvedValue({ data: { profile: created } });
        api.get
            .mockResolvedValueOnce({ data: [profile] })
            .mockResolvedValueOnce({ data: [profile, created] });

        renderProfiles();
        await screen.findAllByText('Provider A');
        fireEvent.click(screen.getByRole('button', { name: 'custom_profiles_add' }));
        fireEvent.change(screen.getByLabelText('api_url_label'), {
            target: { value: 'https://provider-b.example/v1' },
        });
        const modelsInput = screen.getAllByLabelText('api_models_label')
            .find((element) => element.tagName === 'INPUT');
        fireEvent.change(modelsInput, { target: { value: 'model-b' } });
        fireEvent.keyDown(modelsInput, { key: 'Enter', code: 'Enter' });
        fireEvent.click(screen.getByRole('button', { name: 'save' }));

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/api/providers/profiles', expect.objectContaining({
                api_url: 'https://provider-b.example/v1',
                models: ['model-b'],
                display_name: 'custom_profiles_new_name',
            }));
        });
    });

    it('updates the profile and omits an empty API key so the saved key is retained', async () => {
        renderProfiles();
        await screen.findAllByText('Provider A');
        fireEvent.click(screen.getAllByRole('button', { name: 'custom_profiles_edit' })[0]);
        fireEvent.change(screen.getByLabelText('custom_profiles_name_label'), { target: { value: 'Renamed A' } });
        fireEvent.click(screen.getByRole('button', { name: 'save' }));

        await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
            '/api/providers/profiles/profile-provider-a',
            expect.objectContaining({
                display_name: 'Renamed A',
                models: [],
            }),
        ));
        const payload = api.patch.mock.calls[0][1];
        expect(payload).not.toHaveProperty('adapter_id');
        expect(payload).not.toHaveProperty('api_key');
    });

    it('adds a local draft without calling a non-CRUD selection endpoint', async () => {
        renderProfiles();
        await screen.findAllByText('Provider A');
        fireEvent.click(screen.getByRole('button', { name: 'custom_profiles_add' }));

        expect(screen.getByDisplayValue('custom_profiles_new_name')).toBeInTheDocument();
        expect(api.post).not.toHaveBeenCalled();
        expect(api.patch).not.toHaveBeenCalled();
    });

    it('removes a new draft when editing is cancelled', async () => {
        renderProfiles();
        await screen.findAllByText('Provider A');
        fireEvent.click(screen.getByRole('button', { name: 'custom_profiles_add' }));
        expect(screen.getByDisplayValue('custom_profiles_new_name')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'cancel' }));
        expect(screen.queryByDisplayValue('custom_profiles_new_name')).not.toBeInTheDocument();
        expect(screen.getAllByText('Provider A').length).toBeGreaterThan(0);
    });

    it('does not switch cards or lose dirty edits', async () => {
        const secondProfile = { ...profile, profile_id: 'profile-provider-b', display_name: 'Provider B' };
        api.get.mockResolvedValue({ data: [profile, secondProfile] });
        renderProfiles();
        await screen.findAllByText('Provider A');
        const editButtons = screen.getAllByRole('button', { name: 'custom_profiles_edit' });
        const secondEditButton = editButtons[1];
        fireEvent.click(editButtons[0]);
        fireEvent.change(screen.getByLabelText('custom_profiles_name_label'), { target: { value: 'Changed A' } });
        fireEvent.click(secondEditButton);

        expect(screen.getByDisplayValue('Changed A')).toBeInTheDocument();
        expect(screen.queryByDisplayValue('Provider B')).not.toBeInTheDocument();
        expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
            message: 'settings_unsaved_changes_message',
        }));
    });

    it('requires confirmation and clears selection when deleting the active profile', async () => {
        api.get
            .mockResolvedValueOnce({ data: [profile] })
            .mockResolvedValueOnce({ data: [] });
        renderProfiles();
        await screen.findAllByText('Provider A');
        fireEvent.click(screen.getByRole('button', { name: 'custom_profiles_delete' }));

        await waitFor(() => expect(screen.getByText('custom_profiles_delete_title')).toBeInTheDocument());
        expect(api.delete).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'custom_profiles_delete_confirm' }));

        await waitFor(() => expect(api.delete).toHaveBeenCalledWith(
            '/api/providers/profiles/profile-provider-a',
        ));
        expect(api.patch).not.toHaveBeenCalled();
        expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
            message: 'custom_profiles_deleted',
        }));
    });
});
