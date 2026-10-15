import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useToast } from '../context/ToastContext';
import { MANAGED_ENTITIES, saveDraft, loadDraft, clearDraft, completeDraft, createContext } from '../utils/draftStorage';

export function useManagedOrigin(snapshot, restore, selectCreated) {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const path = location.pathname + location.search;
  const token = location.state?.draftToken;
  // Returning from the destination rereads its saved create result.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const draft = useMemo(() => loadDraft(token, path), [token, path, location.state?.managedAway]);
  const restored = useRef(null);
  const [pending, setPending] = useState(null);
  useEffect(() => {
    if (!draft) return;
    const phase = `${token}:${Boolean(location.state?.managedAway)}`;
    if (restored.current !== phase) { restore(draft.data); restored.current = phase; }
    // One navigation transition restores state, then selects after the next commit.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!location.state?.managedAway) setPending({ token, draft });
    // Restore once per navigation token, never on ordinary form edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, draft, location.state?.managedAway]);
  useEffect(() => {
    if (!pending) return;
    if (pending.draft.created) selectCreated(pending.draft.entity, pending.draft.created);
    try { clearDraft(pending.token); } catch { /* Consumed router state prevents replay if removal fails. */ }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPending(null);
    navigate(path, { replace: true, state: null });
    // Selection runs after restored form state has committed (item autofill reads GST).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);
  const begin = (entity, context = {}, data = snapshot()) => {
    try {
      const key = saveDraft(path, entity, data, context);
      navigate(path, { replace: true, state: { draftToken: key } });
      navigate(MANAGED_ENTITIES[entity].route, { state: { managedCreate: key } });
    } catch (error) { toast.error(`Cannot leave this form: ${error.message}`); }
  };
  return { begin, restoring: Boolean(draft) };
}

export function useManagedDestination(entity) {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const context = createContext(location);
  const active = context?.entity === entity;
  const finish = (record = null) => {
    if (!active) return false;
    try {
      const origin = completeDraft(context.key, entity, record);
      navigate(origin, { replace: true, state: { draftToken: context.key } });
    } catch (error) { toast.error(error.message); }
    return true;
  };
  return { active, context: active ? context.context : {}, finish };
}
