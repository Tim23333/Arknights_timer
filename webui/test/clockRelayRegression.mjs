import {createClockPublisher, createClockReceiver} from '../clockRelay.mjs';

document.getElementById('run').onclick = async () => {
  const result = document.getElementById('result');
  result.textContent = '测试中…';
  // A private test channel prevents synthetic samples reaching actual log pages.
  const name = 'clock-relay-test-' + crypto.randomUUID();
  const seen = [];
  let publisher = createClockPublisher({channel:new BroadcastChannel(name), id:'main-a'});
  publisher.update({gameTime:0, fixedFrame:0, connected:true}, true);
  const receiver = createClockReceiver({channel:new BroadcastChannel(name), id:'log', onChange:value => seen.push(value)});
  const waitFor = async predicate => {
    const deadline = performance.now() + 3000;
    while (!predicate() && performance.now() < deadline) await new Promise(resolve => setTimeout(resolve, 25));
    return predicate();
  };
  try {
    const replay = await waitFor(() => seen.at(-1)?.status === 'shared' && seen.at(-1)?.clock?.fixedFrame === 0);
    publisher.update({gameTime:3.33, fixedFrame:100, connected:true}, true);
    const changed = await waitFor(() => seen.at(-1)?.clock?.fixedFrame === 100);
    publisher.update({gameTime:3.33, fixedFrame:100, connected:true}, false);
    const disconnected = await waitFor(() => seen.at(-1)?.connected === false && seen.at(-1)?.status === 'shared');
    publisher.close();
    const closed = await waitFor(() => seen.at(-1)?.status === 'lost');
    publisher = createClockPublisher({channel:new BroadcastChannel(name), id:'main-b'});
    publisher.update({gameTime:0, fixedFrame:0, connected:true}, true);
    const resumed = await waitFor(() => seen.at(-1)?.status === 'shared' && seen.at(-1)?.clock?.fixedFrame === 0);
    result.textContent = JSON.stringify({passed:replay && changed && disconnected && closed && resumed,
      replay, changed, disconnected, closed, resumed}, null, 2);
  } finally { receiver.close(); publisher.close(); }
};
