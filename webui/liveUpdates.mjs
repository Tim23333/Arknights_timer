/** Coalesce actual snapshots per topic into one browser draw, never extrapolating frames. */
export function createLatestUpdates(schedule, draw, {sessionTopics = [], initialSession = null, initialOrder = null} = {}) {
  const streams = new Map(), versions = new Map(), pending = new Map();
  const scopedTopics = new Set(sessionTopics), retiredSessions = new Set(), retiredOrigins = new Set();
  let session = initialSession;
  let order = initialOrder;
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
      const incomingSession = message.data?.meta?.sessionId;
      if (scopedTopics.has(message.topic) && typeof incomingSession === 'string') {
        const incomingOrder = message.data.meta;
        if (typeof incomingOrder.sessionOrigin === 'string' && Number.isSafeInteger(incomingOrder.sessionOrdinal)) {
          if (retiredOrigins.has(incomingOrder.sessionOrigin)) return;
          if (order?.sessionOrigin === incomingOrder.sessionOrigin) {
            if (incomingOrder.sessionOrdinal < order.sessionOrdinal
                || (incomingOrder.sessionOrdinal === order.sessionOrdinal && session !== incomingSession)) return;
          } else if (order?.sessionOrigin) retiredOrigins.add(order.sessionOrigin);
          order = incomingOrder;
        }
        if (retiredSessions.has(incomingSession)) return;
        if (session !== incomingSession) {
          if (session !== null) retiredSessions.add(session);
          session = incomingSession;
          // SSE channels are not one atomic batch. Any first new-session topic
          // invalidates the other slots before drawing; late old-channel data
          // must not resurrect a retired session. Frame differences within one
          // session remain legal and retain their individual provenance.
          for (const topic of scopedTopics) pending.set(topic, null);
        }
      }
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
