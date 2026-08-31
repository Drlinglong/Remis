const formatValidationItem = (item) => {
    if (!item || typeof item !== 'object') return '';
    const field = Array.isArray(item.loc) ? item.loc.at(-1) : '';
    const message = typeof item.msg === 'string' ? item.msg : '';
    if (!message) return '';
    return field ? `${field}: ${message}` : message;
};

const formatDetail = (detail) => {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map(formatValidationItem).filter(Boolean).join('; ');
    }
    if (detail && typeof detail === 'object') {
        if (typeof detail.message === 'string') return detail.message;
        if (typeof detail.msg === 'string') return detail.msg;
        if (typeof detail.code === 'string') return detail.code;
    }
    return '';
};

export const formatApiError = (error, fallback = 'Request failed') => (
    formatDetail(error?.response?.data?.detail)
    || (typeof error?.message === 'string' ? error.message : '')
    || fallback
);
