import {test} from 'node:test';
import assert from 'node:assert/strict';
import {paginate} from '../pagination.mjs';

test('paging preserves source rows and global row numbers', () => {
  const rows = Array.from({length: 27}, (_, i) => ({id: i}));
  const result = paginate(rows, 10, 2);
  assert.equal(result.offset, 10);
  assert.equal(result.pages, 3);
  assert.deepEqual(result.items.map(row => row.id), [10,11,12,13,14,15,16,17,18,19]);
  assert.equal(rows.length, 27);
});
test('custom count, shrinking datasets, all and empty results remain valid', () => {
  assert.equal(paginate([1,2,3], 2, 10).page, 2);
  assert.deepEqual(paginate([1,2,3], 0, 10).items, [1,2,3]);
  assert.equal(paginate([], 15, 10).page, 1);
  assert.deepEqual(paginate([1,2,3], 1, 2).items, [2]);
  assert.equal(paginate([1], NaN, NaN).page, 1);
});
