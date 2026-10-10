import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDetailSelection} from '../detailSelection.mjs';

test('replacing entity details with a guide releases the backend target exactly once', async () => {
  const calls = [];
  const selection = createDetailSelection(async target => calls.push(target));
  await selection.replace({kind:'enemy', id:'e'});
  await selection.replace(null);
  await selection.replace(null);
  assert.deepEqual(calls, [{kind:'enemy', id:'e'}, {kind:'enemy', id:null}]);
});

test('late selection completion cannot clear the replacement target', async () => {
  // ROOT CAUSE: drawer replacement lost the old target; asynchronous selection
  // and cancellation must share ordered ownership, not fire independent HTTP.
  const calls = [];
  let finish;
  const selection = createDetailSelection(target => {
    calls.push(target);
    return calls.length === 1 ? new Promise(resolve => { finish = resolve; }) : Promise.resolve();
  });
  const first = selection.replace({kind:'enemy', id:'a'});
  await Promise.resolve();
  const second = selection.replace({kind:'character', id:'b'});
  finish();
  await first;
  await second;
  assert.deepEqual(calls, [{kind:'enemy', id:'a'}, {kind:'enemy', id:null}, {kind:'character', id:'b'}]);
  await selection.replace(null);
  assert.deepEqual(calls.at(-1), {kind:'character', id:null});
});

test('superseded requests are skipped and failed selection is conservatively released', async () => {
  const calls = [], errors = [];
  const selection = createDetailSelection(async target => {
    calls.push(target);
    if (target.id === 'b') throw new Error('request failed after possible application');
  }, error => errors.push(error.message));
  const old = selection.replace({kind:'enemy', id:'a'});
  const current = selection.replace({kind:'enemy', id:'b'});
  await old;
  await current;
  await selection.replace(null);
  assert.deepEqual(calls, [{kind:'enemy', id:'b'}, {kind:'enemy', id:null}]);
  assert.equal(errors.length, 1);
});

test('failed cancellation blocks replacement until the next transition retries it', async () => {
  const calls = [], errors = [];
  let fail = true;
  const selection = createDetailSelection(async target => {
    calls.push(target);
    if (target.id === null && fail) { fail = false; throw new Error('cancel failed'); }
  }, error => errors.push(error.message));
  await selection.replace({kind:'enemy', id:'a'});
  await selection.replace({kind:'enemy', id:'b'});
  assert.deepEqual(calls, [{kind:'enemy', id:'a'}, {kind:'enemy', id:null}]);
  await selection.replace({kind:'enemy', id:'b'});
  assert.deepEqual(calls.slice(2), [{kind:'enemy', id:null}, {kind:'enemy', id:'b'}]);
  assert.equal(errors.length, 1);
});

test('closing while selection is pending still cancels it after completion', async () => {
  const calls = [];
  let finish;
  const selection = createDetailSelection(target => {
    calls.push(target);
    return calls.length === 1 ? new Promise(resolve => { finish = resolve; }) : Promise.resolve();
  });
  const pending = selection.replace({kind:'enemy', id:'a'});
  await Promise.resolve();
  const closed = selection.replace(null);
  finish();
  await pending;
  await closed;
  assert.deepEqual(calls, [{kind:'enemy', id:'a'}, {kind:'enemy', id:null}]);
});
