import { useCallback, useEffect, useState } from 'react';
import api from '../../utils/api';
import { normalizeArrayPayload } from '../../utils/payload';

export const CUSTOM_PROVIDER_PROFILES_ENDPOINT = '/api/providers/profiles';

const normalizeProfile = (profile) => ({
    ...profile,
    profile_id: profile.profile_id || profile.id,
    display_name: profile.display_name || profile.name || 'Custom Provider',
    adapter_id: profile.adapter_id || 'your_favourite_api',
});

export const normalizeCustomProviderProfilesResponse = (data) => {
    const profiles = Array.isArray(data)
        ? data
        : normalizeArrayPayload(data, ['profiles', 'items', 'data', 'results']);
    const normalizedProfiles = profiles
        .filter((profile) => profile && (profile.profile_id || profile.adapter_id))
        .map(normalizeProfile)
        .filter((profile) => profile.profile_id);

    return {
        profiles: normalizedProfiles,
    };
};

const getProfileFromResponse = (data) => {
    const candidate = data?.profile || data?.item || data?.data || data;
    return candidate?.profile_id || candidate?.adapter_id
        ? normalizeProfile(candidate)
        : null;
};

export const useCustomProviderProfiles = () => {
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const refresh = useCallback(async () => {
        setError(null);
        try {
            const response = await api.get(CUSTOM_PROVIDER_PROFILES_ENDPOINT);
            const result = normalizeCustomProviderProfilesResponse(response.data);
            setProfiles(result.profiles);
            return result;
        } catch (requestError) {
            setError(requestError);
            throw requestError;
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh().catch(() => undefined);
    }, [refresh]);

    const createProfile = useCallback(async (payload) => {
        const response = await api.post(CUSTOM_PROVIDER_PROFILES_ENDPOINT, payload);
        const profile = getProfileFromResponse(response.data);
        await refresh();
        return profile;
    }, [refresh]);

    const updateProfile = useCallback(async (profileId, payload) => {
        const response = await api.patch(
            `${CUSTOM_PROVIDER_PROFILES_ENDPOINT}/${encodeURIComponent(profileId)}`,
            payload,
        );
        await refresh();
        return getProfileFromResponse(response.data);
    }, [refresh]);

    const deleteProfile = useCallback(async (profileId) => {
        await api.delete(`${CUSTOM_PROVIDER_PROFILES_ENDPOINT}/${encodeURIComponent(profileId)}`);
        await refresh();
    }, [refresh]);

    return {
        profiles,
        loading,
        error,
        refresh,
        createProfile,
        updateProfile,
        deleteProfile,
    };
};
