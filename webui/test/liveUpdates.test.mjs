import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createLatestUpdates} from '../liveUpdates.mjs';

test('100 clock samples schedule one draw, retaining only actual latest sample', () => {
  const draws = [], scheduled = [];
  const updates = createLatestUpdates(callback => scheduled.push(callback), values => draws.push(values));
  for (let sequence = 1; sequence <= 100; sequence++) updates.receive('clock', {streamId: 'a', sequence, topic: 'clock', data: {fixedFrame: sequence}});
  assert.equal(scheduled.length, 1);
  scheduled.shift()();
  assert.equal(draws[0].clock.fixedFrame, 100);
});

test('reconnect ignores older replay; a restarted server accepts reset sequences', () => {
  const scheduled = [], draws = [];
  const updates = createLatestUpdates(callback => scheduled.push(callback), values => draws.push(values));
  updates.receive('clock', {streamId: 'a', sequence: 10, topic: 'clock', data: {fixedFrame: 10}});
  updates.receive('clock', {streamId: 'a', sequence: 9, topic: 'clock', data: {fixedFrame: 9}});
  scheduled.shift()();
  assert.equal(draws[0].clock.fixedFrame, 10);
  updates.receive('clock', {streamId: 'b', sequence: 1, topic: 'clock', data: null});
  scheduled.shift()();
  assert.equal(draws[1].clock, null);
});
