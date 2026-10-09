// Same-origin browser messaging, never a second backend subscription or a
// persisted game cache. A receiver sticks to one worktable until it disappears.
export const clockChannelName = 'timeline-worktable-clock-v1';

/** Publish the worktable's accepted clock snapshots, independently of DOM drawing.
 * Heartbeats establish window presence only: they never advance game time/frame.
 * The channel and timer boundary can be supplied by offline regression tests. */
export function createClockPublisher({channel, id, timers = globalThis}) {
  let clock = null, connected = false, closed = false;
  const send = () => {
    if (!closed) channel.postMessage({type:'snapshot', sender:id, clock, connected});
  };
  channel.onmessage = event => { if (event.data?.type === 'request') send(); };
  const heartbeat = timers.setInterval(send, 1000);
  return {
    update(value, active) { if (closed) return; clock = value; connected = active; send(); },
    close() {
      if (closed) return;
      closed = true;
      channel.postMessage({type:'closed', sender:id});
      timers.clearInterval(heartbeat); channel.close();
    },
  };
}

/** Receive real snapshots from an existing same-origin worktable.
 * Late windows request its current slot. No source means waiting/last-known,
 * not a fallback network read. Local timeout measures relay presence, not game
 * freshness; an unchanged paused clock remains valid with worktable heartbeats. */
export function createClockReceiver({channel, id, onChange, now = () => performance.now(), timers = globalThis}) {
  let sender = null, lastSeen = 0, clock = null, closed = false, status = 'waiting';
  const request = () => channel.postMessage({type:'request', sender:id});
  const lost = () => {
    sender = null;
    if (status === 'waiting' || status === 'lost') return;
    status = 'lost'; onChange({clock, connected:false, status});
  };
  channel.onmessage = event => {
    if (closed) return;
    const message = event.data;
    if (!message || typeof message.sender !== 'string' || message.sender === id) return;
    if (message.type === 'closed' && sender === message.sender) { lost(); request(); return; }
    if (message.type !== 'snapshot' || typeof message.connected !== 'boolean'
        || (message.clock !== null && (typeof message.clock !== 'object' || Array.isArray(message.clock)))) return;
    if (sender && sender !== message.sender && now() - lastSeen < 5000) return;
    sender = message.sender; lastSeen = now(); clock = message.clock; status = 'shared';
    onChange({clock, connected:message.connected, status});
  };
  onChange({clock, connected:false, status});
  // Also recover after a crashed/reloaded/background-throttled worktable. No
  // browser clock is ever converted into a predicted game value.
  const heartbeat = timers.setInterval(() => {
    if (sender && now() - lastSeen >= 5000) lost();
    if (!sender) request();
  }, 1000);
  request();
  return {close() { closed = true; timers.clearInterval(heartbeat); channel.close(); }};
}
