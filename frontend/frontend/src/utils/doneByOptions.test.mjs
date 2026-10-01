import test from 'node:test';
import assert from 'node:assert/strict';
import { doneByOptions } from './doneByOptions.js';

test('new transactions offer only active master names', () => {
  const options = doneByOptions([{ name: 'Rahul', is_active: false }, { name: 'Amit', is_active: true }]);
  assert.deepEqual(options.map((row) => row.value), ['', 'Amit']);
});
test('historical inactive or renamed snapshot displays but cannot be newly selected', () => {
  const options = doneByOptions([{ name: 'Rahul Patel', is_active: true }], 'Rahul');
  assert.deepEqual(options[1], { value: 'Rahul', label: 'Rahul (saved)', disabled: true });
  assert.equal(options[2].value, 'Rahul Patel');
});
test('active saved name is offered once', () => {
  assert.equal(doneByOptions([{ name: 'Rahul', is_active: true }], 'Rahul').length, 2);
});
test('empty master has no hard-coded fallback', () => {
  assert.deepEqual(doneByOptions([]), [{ value: '', label: 'Select Done By' }]);
});
