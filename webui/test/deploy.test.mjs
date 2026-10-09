import test from 'node:test';
import assert from 'node:assert/strict';
import {deployView} from '../model.mjs';

// ROOT CAUSE:
// The renderer treated the stage topic's transport wrapper as stage information
// and used raw event keys/enums as labels. Presentation must unwrap stage only;
// the protocol payload remains intact for WS, export and raw JSON inspection.
test('stage cards show Chinese stage facts, not stage/squad/meta wrapper objects', () => {
  const payload = {stage: {code: '1-7', name: '暴君', stageId: 'main_01-07', levelId: 'level_main_01-07'}, squad: [{charName: '芬'}], meta: {sourceFrame: 30}};
  const original = structuredClone(payload);
  const view = deployView(payload, {});
  assert.deepEqual(view.facts.map(item => item.label), ['关卡编号', '关卡名称', '关卡标识', '关卡资源标识']);
  assert.deepEqual(view.facts.map(item => item.value), ['1-7', '暴君', 'main_01-07', 'level_main_01-07']);
  assert.equal(view.facts.some(item => ['stage', 'squad', 'meta'].includes(item.key)), false);
  assert.deepEqual(payload, original);
  assert.equal(view.rows.length, 0);
  assert.equal(view.columns.some(item => item.label === '操作'), true);
});

test('zero operation frame is visible and absence is explained, never estimated from timestamp', () => {
  const view = deployView({}, {events: [{timestamp: 0, frame: 0}, {timestamp: 12.599988}]});
  assert.equal(view.rows[0].values.frame, 'F0');
  assert.equal(view.rows[1].values.frame, '不可用（无对应时钟采样）');
});

test('all current operation fields and enums have Chinese display, including frame matching', () => {
  const event = {timestamp: 1.25, frame: 38, op: 0, opName: 'SPAWN', charName: '芬', charId: 'char_123_fang', charInstId: 7, uniqueId: 7, direction: 0, directionName: 'UP', gridCol: 0, gridRow: 2, extraInfo: '', frameSource: 'timerCacheExact', frameSampleTime: 1.25, frameTimeDelta: 0};
  const payload = {events: [event], journal: [event], meta: {sourceFrame: 38}};
  const original = structuredClone(payload);
  const view = deployView({}, payload);
  assert.equal(view.columns.length, Object.keys(event).length);
  assert.equal(view.columns.every(item => /[\u4e00-\u9fff]/.test(item.label)), true);
  assert.equal(view.columns.find(item => item.key === 'uniqueId').label, '干员唯一标识');
  assert.equal(view.rows[0].values.timestamp, '1.250');
  assert.equal(view.rows[0].values.frame, 'F38');
  assert.equal(view.rows[0].values.op, '部署');
  assert.equal(view.rows[0].values.opName, '部署');
  assert.equal(view.rows[0].values.direction, '上');
  assert.equal(view.rows[0].values.directionName, '上');
  assert.equal(view.rows[0].values.gridCol, '0');
  assert.equal(view.rows[0].values.frameSource, '计时器缓存精确匹配');
  assert.equal(view.rows[0].values.frameTimeDelta, '0.000000');
  assert.deepEqual(payload, original);
});

test('deployment and skill from the same operator stay separate; squad names resolve without showing the squad object', () => {
  const stage = {squad: [{charInstId: 7, charName: '芬'}]};
  const events = [{uniqueId: 7, op: 0, charName: '', direction: 4}, {uniqueId: 7, op: 2, charName: '', direction: null}, {uniqueId: 8, op: 1, charId: 'char_8'}, {op: 3}];
  const view = deployView(stage, {events});
  assert.equal(new Set(view.rows.map(row => row.id)).size, 4);
  assert.equal(view.rows[0].values.charName, '芬');
  assert.equal(view.rows[1].values.charName, '芬');
  assert.equal(view.rows[1].values.op, '技能');
  assert.equal(view.rows[2].values.op, '撤退');
  assert.equal(view.rows[2].values.charName, 'char_8');
  assert.equal(view.rows[3].values.op, '作弊');
  assert.equal(view.rows[0].values.direction, '无');
  assert.equal(view.rows[1].values.direction, '—');
});

test('unavailable values are not invented, and future fields/enums remain inspectable', () => {
  const view = deployView({meta: {collectionState: 'unavailable'}}, {events: [{timestamp: null, frame: null, op: 99, direction: 99, futureField: false, frameSource: 'timerCacheInterpolated'}]});
  assert.equal(view.facts.every(item => item.value === '—'), true);
  assert.equal(view.rows[0].values.timestamp, '—');
  assert.equal(view.rows[0].values.frame, '不可用（无对应时钟采样）');
  assert.equal(view.rows[0].values.gridCol, '—');
  assert.equal(view.rows[0].values.charName, '—');
  assert.equal(view.rows[0].values.op, '未知操作（99）');
  assert.equal(view.rows[0].values.direction, '未知朝向（99）');
  assert.equal(view.rows[0].values.frameSource, '计时器缓存插值匹配');
  assert.equal(view.rows[0].values.futureField, '否');
  assert.equal(view.columns.find(item => item.key === 'futureField').label, '未识别字段（futureField）');
  assert.equal(deployView({}, {events: [{frameSource: 'toString'}]}).rows[0].values.frameSource, 'toString');
});
