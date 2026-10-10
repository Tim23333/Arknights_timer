import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createClockPublisher, createClockReceiver} from '../clockRelay.mjs';

// ROOT CAUSE: logWindow previously opened its own clock SSE. Extra windows
// could exhaust HTTP connections despite the worktable already having a clock.
// Exercise the browser-message boundary without a backend or game connection.
function harness() {
  let time = 0;
  const ports = new Set(), ticks = new Set();
  const timers = {setInterval:callback => { ticks.add(callback); return callback; }, clearInterval:callback => ticks.delete(callback)};
  const channel = () => {
    const port = {onmessage:null, postMessage(data) { for (const peer of ports) if (peer !== port) peer.onmessage?.({data:structuredClone(data)}); }, close() { ports.delete(port); }};
    ports.add(port); return port;
  };
  return {channel, timers, now:() => time, advance(ms) { time += ms; for (const tick of [...ticks]) tick(); }, ports, ticks};
}

test('independent log entry has no backend clock transport or fallback', async () => {
  // Guard the original integration failure in addition to the behavioral tests:
  // a future standalone entry must not quietly recreate the removed clock SSE.
  const entry = await readFile(new URL('../logWindow.mjs', import.meta.url), 'utf8');
  const relay = await readFile(new URL('../clockRelay.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(entry, /EventSource|WebSocket|\/api\/stream\//);
  assert.doesNotMatch(relay, /fetch\(|EventSource|WebSocket/);
  assert.match(entry, /createClockReceiver/);
});

test('log clocks replay the main snapshot, update while not drawing, and preserve zero/null', () => {
  const h = harness(), seen = [];
  const main = createClockPublisher({channel:h.channel(), id:'main', timers:h.timers});
  main.update({gameTime:0, fixedFrame:0, connected:true}, true);
  const log = createClockReceiver({channel:h.channel(), id:'log', timers:h.timers, now:h.now, onChange:value => seen.push(value)});
  assert.equal(seen.at(-1).clock.fixedFrame, 0);
  assert.equal(seen.at(-1).status, 'shared');
  main.update({gameTime:10, fixedFrame:300, connected:true}, true);
  assert.equal(seen.at(-1).clock.fixedFrame, 300);
  main.update(null, true);
  assert.equal(seen.at(-1).clock, null);
  log.close(); main.close();
  assert.equal(h.ports.size, 0);
  assert.equal(h.ticks.size, 0);
});

test('disconnect is not live, main close keeps last known data and a replacement can resume', () => {
  const h = harness(), seen = [];
  const main = createClockPublisher({channel:h.channel(), id:'a', timers:h.timers});
  const log = createClockReceiver({channel:h.channel(), id:'log', timers:h.timers, now:h.now, onChange:value => seen.push(value)});
  main.update({fixedFrame:100, gameTime:3}, true);
  main.update({fixedFrame:100, gameTime:3}, false);
  assert.equal(seen.at(-1).connected, false);
  main.close();
  assert.equal(seen.at(-1).status, 'lost');
  assert.equal(seen.at(-1).clock.fixedFrame, 100);
  const replacement = createClockPublisher({channel:h.channel(), id:'b', timers:h.timers});
  replacement.update({fixedFrame:0, gameTime:0}, true);
  assert.equal(seen.at(-1).status, 'shared');
  assert.equal(seen.at(-1).clock.fixedFrame, 0);
  replacement.close(); log.close();
});

test('stalled publisher expires without treating unchanged paused game frames as stale', () => {
  const h = harness(), seen = [];
  const main = createClockPublisher({channel:h.channel(), id:'main', timers:h.timers});
  main.update({fixedFrame:100, gameTime:3}, true);
  const port = h.channel();
  const log = createClockReceiver({channel:port, id:'log', timers:h.timers, now:h.now, onChange:value => seen.push(value)});
  h.advance(6000);
  assert.equal(seen.at(-1).status, 'shared');
  // Simulate a killed/frozen tab: no pagehide/bye and no heartbeat or response.
  h.ports.delete([...h.ports].find(item => item !== port));
  h.ticks.delete([...h.ticks][0]);
  h.advance(6000);
  assert.equal(seen.at(-1).status, 'lost');
  assert.equal(seen.at(-1).clock.fixedFrame, 100);
  main.close(); log.close();
});

test('multiple worktables do not alternate frames and closed receiver ignores messages', () => {
  const h = harness(), seen = [];
  const a = createClockPublisher({channel:h.channel(), id:'a', timers:h.timers});
  a.update({fixedFrame:100}, true);
  const log = createClockReceiver({channel:h.channel(), id:'log', timers:h.timers, now:h.now, onChange:value => seen.push(value)});
  const b = createClockPublisher({channel:h.channel(), id:'b', timers:h.timers});
  b.update({fixedFrame:50}, true);
  assert.equal(seen.at(-1).clock.fixedFrame, 100);
  a.close(); b.update({fixedFrame:51}, true);
  assert.equal(seen.at(-1).clock.fixedFrame, 51);
  log.close(); const length = seen.length;
  b.update({fixedFrame:52}, true);
  assert.equal(seen.length, length);
  b.close();
});
