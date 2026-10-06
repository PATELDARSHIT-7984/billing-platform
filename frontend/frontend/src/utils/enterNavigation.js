// Opt in at a form/container, never at individual fields. Nested dialogs/forms
// are separate boundaries even when React bubbles their events to the parent.
const BOUNDARY = 'form, [data-enter-navigation], [role="dialog"]';
const TEXT_INPUT_TYPES = new Set(['text', 'number', 'email', 'tel', 'url', 'search', 'password']);

export function handleEnterNavigation(event) {
  const { target, currentTarget: container } = event;
  if (event.key !== 'Enter' || event.defaultPrevented || event.isComposing
      || event.nativeEvent?.isComposing || event.keyCode === 229
      || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey
      || target.tagName !== 'INPUT' || !TEXT_INPUT_TYPES.has(target.type)
      || target.closest('[role="combobox"], [aria-haspopup], [data-enter-navigation-ignore]')
      || target.hasAttribute('list') || target.closest(BOUNDARY) !== container) return;

  const fields = Array.from(container.querySelectorAll('input, select, textarea'))
    .filter((field) => {
      if (field.closest(BOUNDARY) !== container || field.matches(':disabled')
          || field.readOnly || field.tabIndex < 0
          || ['hidden', 'button', 'submit', 'reset', 'image'].includes(field.type)
          || field.closest('[hidden], [inert]') || !field.getClientRects().length
          || (field.form && field.form !== target.form)) return false;
      const visibility = field.ownerDocument.defaultView.getComputedStyle(field).visibility;
      return visibility !== 'hidden' && visibility !== 'collapse';
    })
    // Positive tabindex precedes normal DOM order; stable sort preserves ties.
    .sort((a, b) => (a.tabIndex || Infinity) - (b.tabIndex || Infinity));

  const index = fields.indexOf(target);
  if (index < 0) return;
  for (const next of fields.slice(index + 1)) {
    next.focus();
    if (next.ownerDocument.activeElement === next) {
      event.preventDefault();
      return;
    }
  }
  // No wrap: leave the last field's existing submit/default behavior intact.
}
