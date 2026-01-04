import { useState, useEffect } from 'react';

/**
 * A hook to persist state to localStorage/sessionStorage
 * @param {string} key The storage key
 * @param {any} initialValue The default value
 * @param {string} storageType 'local' or 'session'
 * @returns [storedValue, setValue]
 */
export const usePersistentState = (key, initialValue, storageType = 'session') => {
    const storage = storageType === 'local' ? localStorage : sessionStorage;

    const [storedValue, setStoredValue] = useState(() => {
        try {
            const item = storage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch (error) {
            console.error(`Error reading storage key "${key}":`, error);
            return initialValue;
        }
    });

    const setValue = (value) => {
        try {
            // Allow value to be a function so we have same API as useState
            const valueToStore = value instanceof Function ? value(storedValue) : value;
            setStoredValue(valueToStore);
            storage.setItem(key, JSON.stringify(valueToStore));
        } catch (error) {
            console.error(`Error writing storage key "${key}":`, error);
        }
    };

    return [storedValue, setValue];
};
