import test from 'node:test';
import assert from 'node:assert/strict';
import {createFieldDisplay} from '../fieldDisplay.mjs';

const columns = [{key:'hp'}, {key:'sp'}];
const policy = {generation:0, fields:[{id:'enemy.hp', collect:true, display:true}, {id:'enemy.sp', collect:true, display:true}]};
const context = {kind:'enemy', policy, precision:2};
const text = (row, column) => row.columns?.[column.key] ?? '不可用';
const sample = (frame, state = 'current', hp = '10/20') => ({
  meta:{sessionId:'a', policyGeneration:0, sourceFrame:frame, collectionState:'current'},
  items:[{id:'e1', columns:{hp, sp:'0/15'}, fieldStates:{
    'enemy.hp':{collectionState:state, sourceFrame:state === 'current' ? frame : null},
    'enemy.sp':{collectionState:'current', sourceFrame:frame},
  }}],
});

test('transient failed field retains only its own last valid text and original frame', () => {
  const display = createFieldDisplay();
  display.project(sample(100), context, columns, text, 0);
  const failure = sample(101, 'unavailable', '不可用');
  const unchanged = structuredClone(failure);
  const view = display.project(failure, context, columns, text, 100);
  const hp = view.cell(view.rows[0], columns[0]);
  assert.equal(hp.text, '10/20');
  assert.equal(hp.freshness, 'last_known');
  assert.match(hp.title, /非当前值.*100/);
  assert.equal(view.cell(view.rows[0], columns[1]).text, '0/15');
  assert.deepEqual(failure, unchanged);
  const healthy = display.project(sample(102, 'current', '9/20'), context, columns, text, 120);
  assert.equal(healthy.cell(healthy.rows[0], columns[0]).text, '9/20');
  assert.equal(healthy.cell(healthy.rows[0], columns[0]).freshness, 'current');
});

test('repeated failures cannot extend the 500ms retention or revive expired cache', () => {
  const display = createFieldDisplay();
  display.project(sample(100), context, columns, text, 0);
  const failure = sample(101, 'unavailable', '不可用');
  let view = display.project(failure, context, columns, text, 499);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '10/20');
  assert.equal(view.expiresAt, 500);
  view = display.project(failure, context, columns, text, 500);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '不可用');
  assert.equal(view.heldCount, 0);
});

test('session, policy generation, precision and stop events clear retained values', () => {
  for (const change of ['session', 'policy', 'precision', 'stop']) {
    const display = createFieldDisplay();
    display.project(sample(100), context, columns, text, 0);
    const failure = sample(101, 'unavailable', '不可用');
    let options = context;
    if (change === 'session') failure.meta.sessionId = 'b';
    if (change === 'policy') { failure.meta.policyGeneration = 1; options = {...context, policy:{...policy, generation:1}}; }
    if (change === 'precision') options = {...context, precision:3};
    if (change === 'stop') failure.meta.reason = 'source_stopped';
    const view = display.project(failure, options, columns, text, 100);
    assert.equal(view.cell(view.rows[0], columns[0]).text, '不可用', change);
  }
});

test('disabled, never sampled, removed and different entities do not borrow old values', () => {
  const display = createFieldDisplay();
  display.project(sample(100), context, columns, text, 0);
  const failure = sample(101, 'not_collected', '未采集');
  let view = display.project(failure, context, columns, text, 100);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '未采集');
  failure.items[0].id = 'e2'; failure.items[0].fieldStates['enemy.hp'].collectionState = 'unavailable';
  failure.items[0].columns.hp = '不可用';
  view = display.project(failure, context, columns, text, 150);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '不可用');
  failure.items[0].id = 'e1';
  view = display.project(failure, context, columns, text, 200);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '不可用');
});

test('whole invalid frame keeps topology briefly but not the claim of current data', () => {
  const display = createFieldDisplay();
  display.project(sample(100), context, columns, text, 0);
  const failed = {meta:{...sample(101).meta, collectionState:'unavailable', frameConsistent:false}, items:[]};
  const view = display.project(failed, context, columns, text, 100);
  assert.equal(view.rows[0].id, 'e1');
  assert.equal(view.cell(view.rows[0], columns[0]).freshness, 'last_known');
  assert.equal(display.project(failed, context, columns, text, 500).rows.length, 0);
});

test('pagination and repeated rendering are not a new successful sample', () => {
  const display = createFieldDisplay();
  const first = sample(100);
  display.project(first, context, columns, text, 0);
  display.project(first, context, columns, text, 450);
  const view = display.project(sample(101, 'unavailable', '不可用'), context, columns, text, 550);
  assert.equal(view.cell(view.rows[0], columns[0]).text, '不可用');
});

test('an explicitly unknown source frame is never replaced by the batch frame', () => {
  const display = createFieldDisplay();
  const first = sample(100);
  first.items[0].fieldStates['enemy.hp'].sourceFrame = null;
  display.project(first, context, columns, text, 0);
  const view = display.project(sample(101, 'unavailable', '不可用'), context, columns, text, 100);
  assert.match(view.cell(view.rows[0], columns[0]).title, /来源帧 —/);
  assert.doesNotMatch(view.cell(view.rows[0], columns[0]).title, /100/);
});

test('capture/display policy changes immediately discard a field cache', () => {
  for (const setting of ['collect', 'display']) {
    const display = createFieldDisplay();
    display.project(sample(100), context, columns, text, 0);
    const disabled = {...context, policy:{...policy, fields:policy.fields.map(field =>
      field.id === 'enemy.hp' ? {...field, [setting]:false} : field)}};
    const view = display.project(sample(101), disabled, columns, text, 100);
    assert.equal(view.cell(view.rows[0], columns[0]).text, setting === 'collect' ? '未采集' : '未展示');
    const next = display.project(sample(102, 'unavailable', '不可用'), context, columns, text, 150);
    assert.equal(next.cell(next.rows[0], columns[0]).text, '不可用');
  }
});
