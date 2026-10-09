import test from 'node:test';
import assert from 'node:assert/strict';
import {columnWidths} from '../tableLayout.mjs';

// ROOT CAUSE:
// max-content layout recalculated geometry when live values or visible rows
// changed. Default sizing must depend only on field definitions, not samples;
// explicitly fitted widths belong to the field key, never its display index.
test('default widths reuse desktop column metadata without depending on samples', () => {
  const columns = [{key:'name', label:'名称', width:130}, {key:'hp', label:'血量', width:185}];
  const original = structuredClone(columns);
  assert.deepEqual(columnWidths(columns), [130, 185]);
  assert.deepEqual(columns, original);
  assert.deepEqual(columnWidths(columns), [130, 185]);
});

test('hiding, showing and reordering fields preserve fitted widths by key', () => {
  const fitted = new Map([['name', 220], ['hp', 160]]);
  const name = {key:'name', label:'名称', width:130};
  const hp = {key:'hp', label:'血量', width:185};
  assert.deepEqual(columnWidths([name, hp], fitted), [220, 160]);
  assert.deepEqual(columnWidths([hp], fitted), [160]);
  assert.deepEqual(columnWidths([hp, name], fitted), [160, 220]);
  assert.deepEqual(columnWidths([name, hp], fitted), [220, 160]);
});

test('columns without desktop metadata get deterministic defaults', () => {
  assert.deepEqual(columnWidths([{key:'row'}, {key:'detail'}, {key:'value', label:'随机值'}]), [40, 64, 120]);
});

test('unsafe and excessive widths cannot break fixed layout', () => {
  assert.deepEqual(columnWidths([
    {key:'a', width:NaN}, {key:'b', width:Infinity}, {key:'c', width:-1},
    {key:'d', width:0}, {key:'e', width:1}, {key:'f', width:100000},
    {key:'g', width:130.2}, {key:'h', width:'200'},
  ]), [120, 120, 120, 120, 36, 480, 131, 120]);
});
