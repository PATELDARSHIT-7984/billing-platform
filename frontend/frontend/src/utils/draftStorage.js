const PREFIX = 'draft:';

// Saves an in-progress form's data before navigating away (e.g. to a
// "+ Add Party" redirect), so it can be restored when the user comes back.
export function saveDraft(key, data) {
  try {
    sessionStorage.setItem(PREFIX + key, JSON.stringify(data));
  } catch {
    // Storage can fail in private-browsing mode or when full -- the
    // draft is a convenience, not critical, so fail silently.
  }
}

// Reads back a saved draft, or null if none exists / it failed to parse.
export function loadDraft(key) {
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// Removes a draft once it's been restored, so it isn't reused by mistake.
export function clearDraft(key) {
  try {
    sessionStorage.removeItem(PREFIX + key);
  } catch {
    // Ignore -- same reasoning as saveDraft.
  }
}
