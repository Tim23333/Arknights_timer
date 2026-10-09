/** Coalesce actual snapshots per topic into one browser draw, never extrapolating frames. */
export function createLatestUpdates(schedule, draw) {
  const streams = new Map(), versions = new Map(), pending = new Map();
  let scheduled = false;
  return {
    receive(channel, message) {
      if (!message || typeof message.streamId !== 'string' || !Number.isSafeInteger(message.sequence)
          || typeof message.topic !== 'string') return;
      if (streams.get(channel) !== message.streamId) {
        streams.set(channel, message.streamId);
        for (const key of versions.keys()) if (key.startsWith(channel + ':')) versions.delete(key);
      }
      const key = channel + ':' + message.topic;
      if (message.sequence <= (versions.get(key) || 0)) return;
      versions.set(key, message.sequence);
      pending.set(message.topic, message.data);
      if (scheduled) return;
      scheduled = true;
      schedule(() => {
        const values = Object.fromEntries(pending);
        pending.clear(); scheduled = false;
        draw(values);
      });
    },
  };
}
