"""Custom enemy injection for a level.

Allows overriding or adding enemies to a level without touching game data:

    sim = Simulator("level_main_01-01", custom_enemies=[
        {"key": "enemy_1000_gopro", "level": 1, "count": 5,
         "routeIndex": 1, "startTime": 5.0, "interval": 2.0,
         "attributes": {"maxHp": 9999, "atk": 300},   # optional overrides
         "skills": []}                                  # optional override
    ])
"""


class CustomEnemyScheduler:
    """Merges custom enemies into the wave timeline at construction."""

    def __init__(self, battle, custom_enemies):
        self.battle = battle
        self.custom_enemies = list(custom_enemies or [])
        # schedule: (tick, spec) sorted by spawn time
        self._schedule = []
        for spec in self.custom_enemies:
            t = float(spec.get("startTime", 0.0))
            count = int(spec.get("count", 1))
            interval = float(spec.get("interval", 1.0))
            for i in range(count):
                self._schedule.append(
                    (t + i * interval, dict(spec)))
        self._schedule.sort(key=lambda x: x[0])
        self._idx = 0

    def update(self):
        """Spawn due custom enemies this tick; returns spawned keys."""
        battle = self.battle
        now = battle.tick / 30.0
        spawned = []
        while self._idx < len(self._schedule):
            t, spec = self._schedule[self._idx]
            if t > now + 1e-6:
                break
            self._idx += 1
            enemy = battle.spawn_enemy(
                key=spec.get("key"),
                route_index=spec.get("routeIndex", 0),
                source_ev=None,
                overrides=spec)
            if enemy is not None:
                spawned.append(spec.get("key"))
        return spawned

    def remaining(self):
        return len(self._schedule) - self._idx
