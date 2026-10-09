import test from 'node:test';
import assert from 'node:assert/strict';
import {pieData} from '../model.mjs';

test('pie proportions use valid cumulative values and preserve source records', () => {
  const rows = [{id: 'a', name: '甲', damage: 100}, {id: 'b', name: '乙', damage: 300}, {id: 'c', name: '丙', damage: 0}];
  const original = structuredClone(rows);
  const chart = pieData(rows, 'damage');
  assert.equal(chart.total, 400);
  assert.equal(chart.rows[0].name, '乙');
  assert.equal(chart.rows[0].ratio, 75);
  assert.equal(chart.rows[0].start, 0);
  assert.equal(chart.rows[0].end, 75);
  assert.equal(chart.rows[1].end, 100);
  assert.equal(chart.rows[2].ratio, 0);
  assert.deepEqual(rows, original);
});

test('missing, non-finite or negative values are not invented as zero', () => {
  const chart = pieData([{name: '未采集', damage: null}, {name: '失败', damage: NaN}, {name: '溢出', damage: Infinity}, {name: '异常负数', damage: -1}, {name: '正常', damage: 0}], 'damage');
  assert.equal(chart.rows.length, 1);
  assert.equal(chart.rows[0].name, '正常');
  assert.equal(chart.total, 0);
  assert.equal(chart.missing, 4);
  assert.equal(chart.rows[0].ratio, 0);
  assert.equal(pieData([], 'healing').rows.length, 0);
});
