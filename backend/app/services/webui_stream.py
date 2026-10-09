"""Bounded latest-only SSE snapshots, encoded once and shared by local clients.

Each topic owns one slot, not a queue. A slow socket can skip superseded frames;
it cannot delay a producer or retain an unbounded history. Clock and modules use
separate instances/connections so entity packets never precede a clock packet.
"""
import json
import threading
import uuid


class LatestStream:
    """Own the local stream's sequence, deduplication and shutdown lifecycle."""

    def __init__(self):
        self._condition = threading.Condition()
        self._id = uuid.uuid4().hex
        self._sequence = 0
        self._slots = {}
        self.closed = False

    def publish(self, topic, data):
        # Encode outside the condition: socket writers never hold up producers.
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':'))
        with self._condition:
            previous = self._slots.get(topic)
            if self.closed or (previous and previous[1] == encoded):
                return
            self._sequence += 1
            packet = json.dumps({'streamId': self._id, 'sequence': self._sequence,
                                 'topic': topic}, separators=(',', ':'))[:-1]
            packet = (packet + ',"data":' + encoded + '}').encode('utf-8')
            self._slots[topic] = (self._sequence, encoded, packet)
            self._condition.notify_all()

    def read_after(self, cursor, timeout=1):
        """Return only newer latest slots; an empty cursor bootstraps/reconnects."""
        with self._condition:
            self._condition.wait_for(lambda: self.closed or any(
                slot[0] > cursor.get(topic, 0) for topic, slot in self._slots.items()), timeout)
            return sorted((slot[0], topic, slot[2]) for topic, slot in self._slots.items()
                          if slot[0] > cursor.get(topic, 0))

    def close(self):
        with self._condition:
            self.closed = True
            self._condition.notify_all()
