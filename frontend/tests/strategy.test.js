import test from 'node:test';
import assert from 'node:assert/strict';
import { finiteFrame, normalizeStagePackage, enemyJourney, groupsFromActions,
  buildOperatorLifecycles, operatorStateAt } from '../src/strategy.js';

test('unknown enemy frames remain pending after import and export round trip', () => {
  const input = { enemySpawns: [{ id: 'conditional', startFrame: null, endFrame: null }] };
  const stage = normalizeStagePackage(input);
  assert.equal(stage.enemySpawns[0].startFrame, null);
  assert.equal(normalizeStagePackage(JSON.parse(JSON.stringify(stage))).enemySpawns[0].startFrame, null);
  assert.equal(enemyJourney(stage.enemySpawns[0], { start: { row: 0, col: 0 } }, 30), null);
});

test('blank deploy, withdraw and skill frames do not create frame-zero lifecycle events', () => {
  const rows = ['部署', '撤退', '技能'].map(action_type => ({ action_type, oper: 'operator', frame: null }));
  const life = buildOperatorLifecycles(groupsFromActions(rows))[0];
  assert.deepEqual(life.intervals, []);
  assert.deepEqual(life.skills, []);
  assert.equal(operatorStateAt(life, 0, 30), null);
});

test('frame parser distinguishes unknown values from explicit frame zero', () => {
  for (const value of [null, undefined, '', ' ', false, true, NaN, -1]) assert.equal(finiteFrame(value), null);
  assert.equal(finiteFrame(0), 0);
  assert.equal(finiteFrame('0'), 0);
  assert.equal(finiteFrame(2.6), 3);
});
