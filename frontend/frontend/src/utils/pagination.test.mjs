import test from 'node:test';
import assert from 'node:assert/strict';
import { historyPosition, pageNumbers } from './pagination.js';

test('page buttons cover empty, first, middle and last pages', () => {
  assert.deepEqual(pageNumbers(1, 0), []);
  assert.deepEqual(pageNumbers(1, 1), [1]);
  assert.deepEqual(pageNumbers(2, 3), [1, 2, 3]);
  assert.deepEqual(pageNumbers(1, 18), [1, 2, '…', 18]);
  assert.deepEqual(pageNumbers(9, 18), [1, '…', 8, 9, 10, '…', 18]);
  assert.deepEqual(pageNumbers(18, 18), [1, '…', 17, 18]);
  assert.deepEqual(pageNumbers(1, 1000000), [1, 2, '…', 1000000]);
});

const position = { filterKey: 'old', page: 8, pageSize: 20 };

test('search/date/party filter changes reset page while preserving size', () => {
  for (const filterKey of ['search', 'date', 'party']) {
    assert.deepEqual(historyPosition(position, { type: 'filters', value: filterKey }),
      { filterKey, page: 1, pageSize: 20 });
  }
});

test('all available page sizes reset to page one', () => {
  for (const pageSize of [20, 50, 100]) {
    assert.deepEqual(historyPosition(position, { type: 'size', value: pageSize }),
      { filterKey: 'old', page: 1, pageSize });
  }
});

test('page navigation preserves the active filter and size', () => {
  assert.deepEqual(historyPosition(position, { type: 'page', value: 2 }),
    { filterKey: 'old', page: 2, pageSize: 20 });
});

test('deletion recovers to last valid page including an empty dataset', () => {
  assert.equal(historyPosition(position, { type: 'recover', value: 3 }).page, 3);
  assert.equal(historyPosition(position, { type: 'recover', value: 0 }).page, 1);
  assert.equal(historyPosition(position, { type: 'recover', value: 10 }).page, 8);
  assert.equal(position.page, 8);
});
