import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useBeforeUnload, useBlocker } from 'react-router';
import UnsavedChangesModal from '../components/settings/UnsavedChangesModal';

const UnsavedChangesGuardContext = createContext(null);

const locationKey = (location) => (
  `${location.pathname}${location.search}${location.hash}`
);

export function UnsavedChangesGuardProvider({ children }) {
  const [registrations, setRegistrations] = useState({});
  const [pendingNavigation, setPendingNavigation] = useState(null);
  const registrationsRef = useRef(registrations);
  registrationsRef.current = registrations;

  const register = useCallback((id, isDirty, onDiscard) => {
    setRegistrations((current) => {
      if (
        current[id]?.isDirty === isDirty
        && current[id]?.onDiscard === onDiscard
      ) return current;
      return { ...current, [id]: { isDirty, onDiscard } };
    });
  }, []);

  const unregister = useCallback((id) => {
    setRegistrations((current) => {
      if (!current[id]) return current;
      const next = { ...current };
      delete next[id];
      return next;
    });
  }, []);

  const isDirty = Object.values(registrations).some((registration) => registration.isDirty);
  const shouldBlock = useCallback(({ currentLocation, nextLocation }) => (
    isDirty && locationKey(currentLocation) !== locationKey(nextLocation)
  ), [isDirty]);
  const blocker = useBlocker(shouldBlock);

  useBeforeUnload(useCallback((event) => {
    if (!isDirty) return;
    event.preventDefault();
    event.returnValue = '';
  }, [isDirty]), { capture: true });

  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    setPendingNavigation((current) => current || { type: 'router' });
  }, [blocker.state]);

  const requestNavigation = useCallback((action) => {
    if (typeof action !== 'function') return;
    if (isDirty) setPendingNavigation({ type: 'callback', action });
    else action();
  }, [isDirty]);

  const returnToSettings = useCallback(() => {
    setPendingNavigation(null);
    if (blocker.state === 'blocked') blocker.reset();
  }, [blocker]);

  const discardAndLeave = useCallback(() => {
    Object.values(registrationsRef.current)
      .filter((registration) => registration.isDirty)
      .forEach((registration) => registration.onDiscard?.());
    const action = pendingNavigation?.action;
    setPendingNavigation(null);
    if (blocker.state === 'blocked') blocker.proceed();
    else action?.();
  }, [blocker, pendingNavigation]);

  const contextValue = useMemo(() => ({
    isDirty,
    requestNavigation,
    register,
    unregister,
  }), [isDirty, register, requestNavigation, unregister]);

  return createElement(
    UnsavedChangesGuardContext.Provider,
    { value: contextValue },
    children,
    createElement(UnsavedChangesModal, {
      opened: Boolean(pendingNavigation) || blocker.state === 'blocked',
      onReturn: returnToSettings,
      onDiscard: discardAndLeave,
    }),
  );
}

export function useUnsavedChangesGuard(options = null) {
  const context = useContext(UnsavedChangesGuardContext);
  const id = options?.id;
  const isDirty = Boolean(options?.isDirty);
  const onDiscard = options?.onDiscard;
  const discardRef = useRef(onDiscard);
  discardRef.current = onDiscard;
  const register = context?.register;
  const unregister = context?.unregister;
  const stableDiscard = useCallback(() => discardRef.current?.(), []);

  useEffect(() => {
    if (!register || !unregister || !id) return undefined;
    register(id, isDirty, stableDiscard);
    return () => unregister(id);
  }, [id, isDirty, register, stableDiscard, unregister]);

  return context || {
    isDirty: false,
    requestNavigation: (action) => action(),
  };
}

export function useUnsavedChangesGuardContext() {
  const context = useContext(UnsavedChangesGuardContext);
  if (!context) {
    throw new Error('useUnsavedChangesGuardContext must be used inside UnsavedChangesGuardProvider');
  }
  return context;
}

export { UnsavedChangesGuardContext };
