import assert from 'node:assert/strict';
import test from 'node:test';
import { handleEnterNavigation } from './enterNavigation.js';

// Small DOM doubles keep these handler tests on the existing Node test runner.
// Layout visibility and native browser keyboard behavior need a browser smoke test.
function fixture(specs) {
  const document = { activeElement: null, defaultView: {
    getComputedStyle: (field) => ({ visibility: field.visibility || 'visible' }),
  } };
  const container = { querySelectorAll: () => fields };
  const fields = specs.map((spec = {}) => ({
    tagName: 'INPUT', type: 'text', tabIndex: 0, ownerDocument: document,
    closest(selector) {
      if (selector.startsWith('form,')) return this.boundary || container;
      if (selector === '[hidden], [inert]') return this.hiddenAncestor || null;
      return this.custom || null;
    },
    matches() { return !!this.disabled; },
    hasAttribute(name) { return name === 'list' && !!this.datalist; },
    getClientRects() { return this.hidden ? [] : [{}]; },
    focus() { if (!this.unfocusable) document.activeElement = this; },
    ...spec,
  }));
  function press(index = 0, overrides = {}) {
    document.activeElement = fields[index];
    const event = {
      key: 'Enter', target: fields[index], currentTarget: container,
      preventDefault() { this.defaultPrevented = true; }, ...overrides,
    };
    handleEnterNavigation(event);
    return event;
  }
  return { fields, document, container, press };
}

test('text Enter moves focus to the next field and prevents submission', () => {
  const f = fixture([{}, {}]);
  assert.equal(f.press().defaultPrevented, true);
  assert.equal(f.document.activeElement, f.fields[1]);
});

for (const [name, spec] of Object.entries({
  disabled: { disabled: true }, readonly: { readOnly: true },
  hiddenType: { type: 'hidden' }, hiddenLayout: { hidden: true },
  hiddenAncestor: { hiddenAncestor: true }, hiddenVisibility: { visibility: 'hidden' },
  negativeTabindex: { tabIndex: -1 }, cannotFocus: { unfocusable: true },
})) {
  test(`skips ${name} fields`, () => {
    const f = fixture([{}, spec, {}]);
    assert.equal(f.press().defaultPrevented, true);
    assert.equal(f.document.activeElement, f.fields[2]);
  });
}

test('textarea can receive focus but Enter retains newline behavior', () => {
  const f = fixture([{}, { tagName: 'TEXTAREA', type: 'textarea' }, {}]);
  f.press();
  assert.equal(f.document.activeElement, f.fields[1]);
  assert.equal(f.press(1).defaultPrevented, undefined);
  assert.equal(f.document.activeElement, f.fields[1]);
});

test('select, custom controls, datalists, native pickers and buttons retain Enter', () => {
  for (const spec of [{ tagName: 'SELECT' }, { custom: true }, { datalist: true },
    { type: 'date' }, { type: 'checkbox' }, { tagName: 'BUTTON' }, { type: 'submit' }]) {
    const f = fixture([spec, {}]);
    assert.equal(f.press().defaultPrevented, undefined);
    assert.equal(f.document.activeElement, f.fields[0]);
  }
  const f = fixture([{}, {}]);
  f.press(0, { defaultPrevented: true }); // SearchableSelect already consumed Enter.
  assert.equal(f.document.activeElement, f.fields[0]);
});

test('last field does not wrap or cancel the existing default submit', () => {
  const f = fixture([{}, {}]);
  assert.equal(f.press(1).defaultPrevented, undefined);
  assert.equal(f.document.activeElement, f.fields[1]);
});

test('separate forms and nested dialog boundaries cannot cross-focus', () => {
  const otherBoundary = {};
  const f = fixture([{}, { boundary: otherBoundary }, { form: {} }]);
  assert.equal(f.press().defaultPrevented, undefined);
  assert.equal(f.document.activeElement, f.fields[0]);
  assert.equal(f.press(1).defaultPrevented, undefined);
  assert.equal(f.document.activeElement, f.fields[1]);
});

test('modifier keys, composition and other keys do not navigate', () => {
  const f = fixture([{}, {}]);
  for (const overrides of [{ shiftKey: true }, { ctrlKey: true }, { altKey: true },
    { metaKey: true }, { isComposing: true }, { nativeEvent: { isComposing: true } },
    { keyCode: 229 }, { key: 'Tab' }]) {
    assert.equal(f.press(0, overrides).defaultPrevented, undefined);
    assert.equal(f.document.activeElement, f.fields[0]);
  }
});

test('positive tabindex precedes DOM order without wrapping', () => {
  const f = fixture([{}, { tabIndex: 2 }, { tabIndex: 1 }, {}]);
  f.press(2);
  assert.equal(f.document.activeElement, f.fields[1]);
  f.press(1);
  assert.equal(f.document.activeElement, f.fields[0]);
  f.press(0);
  assert.equal(f.document.activeElement, f.fields[3]);
});

test('no successful focus means no preventDefault', () => {
  const f = fixture([{}, { unfocusable: true }]);
  assert.equal(f.press().defaultPrevented, undefined);
  assert.equal(f.document.activeElement, f.fields[0]);
});
