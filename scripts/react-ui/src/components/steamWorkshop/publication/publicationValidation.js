export const isPublishedFileId = (value) => typeof value === 'string' && /^[1-9][0-9]{0,19}$/.test(value);

export function publicationErrorDetail(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.filter((item) => typeof item?.msg === 'string').map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : '';
      return field ? `${field}: ${item.msg}` : item.msg;
    });
    if (messages.length) return messages.join('; ');
  }
  return detail?.message || error?.message || 'Publication request failed';
}
