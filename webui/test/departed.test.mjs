import test from 'node:test';
import assert from 'node:assert/strict';
import {departedView} from '../model.mjs';

test('raw entity finish codes are localized without reconstructing them from endReason', () => {
  const labels = ['未结束', '到达出口', '生命归零', '坠落', '撤退／撤出', '死亡式撤出', '静默撤出',
    '其他原因', '无伤害来源的生命归零', '被替换', '自身重生', '自身移动式重生', '外部移动式重生'];
  const items = labels.map((label, finishReason) => ({id: String(finishReason), lifecycle: 'departed',
    endReason: 'departed', finishReason}));
  const before = structuredClone(items);
  const rows = departedView(items).rows;
  for (let index = 0; index < labels.length; index++) {
    assert.equal(rows[index].values.reason, labels[index]);
    assert.equal(rows[index].values.finishReason, String(index));
  }
  assert.deepEqual(departedView(items, 'death').rows.map(row => row.id), ['2', '8']);
  assert.deepEqual(departedView(items, 'finish:3').rows.map(row => row.id), ['3']);
  assert.deepEqual(items, before);
  const unknown = departedView([{id: 'u', lifecycle: 'departed', finishReason: 99},
    {id: 'n', lifecycle: 'departed', endReason: 'finish_2', finishReason: null}]).rows;
  assert.equal(unknown[0].values.reason, '未知离场类型（99）');
  assert.equal(unknown[1].values.finishReason, '未观测');
  const disabled = departedView([{id: 'off', lifecycle: 'departed', finishReason: 2,
    fieldStates: {'enemy.finish_reason': {collectionState: 'not_collected'}}}]);
  assert.equal(disabled.rows[0].values.finishReason, '未观测');
  assert.equal(departedView(disabled.rows.map(row => row.item), 'death').rows.length, 0);
});

// ROOT CAUSE: departed includes death, escape and unobserved disappearance.
// Historical HP may be positive; classification must use observed endReason,
// never turn default/missing HP into evidence of death.
test('departed view separates confirmed death and unknown departure without mutating source', () => {
  const items = [{id: 'active', lifecycle: 'active'}, {id: 'pending', lifecycle: 'pending'},
    {id: 'dead', lifecycle: 'departed', name: '敌人', endReason: 'death', endFrame: 0, hp: 10,
      columns: {hp: '10.00/20.00', pos: '(1,2)'}, fieldStates: {'enemy.hp': {collectionState: 'historical', sourceFrame: 90}}},
    {id: 'exit', lifecycle: 'departed', endReason: 'reach_exit', endFrame: 110},
    {id: 'unknown', lifecycle: 'departed', hp: 0}];
  const original = structuredClone(items);
  const view = departedView(items);
  assert.deepEqual(view.rows.map(row => row.id), ['exit', 'dead', 'unknown']);
  assert.equal(view.rows[1].values.endFrame, 'F0');
  assert.equal(view.rows[1].values.reason, '已确认阵亡');
  assert.equal(view.rows[1].values.hp, '10.00/20.00');
  assert.equal(view.rows[1].values.hpFrame, 'F90');
  assert.equal(view.rows[2].values.reason, '离场原因未知');
  assert.equal(view.rows[2].values.hp, '不可用');
  assert.deepEqual(departedView(items, 'death').rows.map(row => row.id), ['dead']);
  assert.deepEqual(departedView(items, 'other').rows.map(row => row.id), ['exit', 'unknown']);
  assert.deepEqual(items, original);
});

test('disabled or failed history properties cannot leak through formatted columns', () => {
  const view = departedView([{id: 'a', lifecycle: 'departed', endReason: 'finish_99',
    columns: {hp: '123/456'}, fieldStates: {'enemy.hp': {collectionState: 'not_collected'}}}]);
  assert.equal(view.rows[0].values.hp, '不可用');
  assert.equal(view.rows[0].values.reason, '其他离场（finish_99）');
});

test('DEAD observed before finish flag changes keeps confirmed classification and raw zero separately', () => {
  const row = departedView([{id: 'dead', lifecycle: 'departed', endReason: 'death', finishReason: 0}]).rows[0];
  assert.equal(row.values.reason, '已确认阵亡');
  assert.equal(row.values.finishReason, '0');
  assert.equal(row.item.finishReason, 0);
  const exit = departedView([{id: 'exit', lifecycle: 'departed', endReason: 'reach_exit', finishReason: 0}]).rows[0];
  assert.equal(exit.values.reason, '进入目标点');
  assert.equal(exit.values.finishReason, '0');
});
