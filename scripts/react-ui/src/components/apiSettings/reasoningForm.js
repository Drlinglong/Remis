export const parseCustomParameters = (value) => {
  const trimmed = value.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('api_custom_parameters_object_error');
  }
  return parsed;
};
