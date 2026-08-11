"""Structured event bus for AI analysis and replay logging."""

import itertools


class Event:
    __slots__ = ("tick", "t", "type", "data", "seq")
    _ids = itertools.count(1)

    def __init__(self, tick, type_, data=None):
        self.tick = tick
        self.t = tick / 30.0
        self.type = type_
        self.data = data or {}
        self.seq = next(Event._ids)

    def to_dict(self):
        return {"seq": self.seq, "tick": self.tick, "t": round(self.t, 4),
                "type": self.type, "data": self.data}


class EventType:
    WAVE_START = "wave_start"
    ACTION = "action"                 # wave action fired (SPAWN/STORY/...)
    ENEMY_SPAWN = "enemy_spawn"
    ENEMY_DEAD = "enemy_dead"
    ENEMY_REACH_EXIT = "enemy_reach_exit"
    ENEMY_STATE = "enemy_state"
    DEPLOY = "deploy"
    WITHDRAW = "withdraw"
    DAMAGE = "damage"
    HEAL = "heal"
    BUFF_APPLIED = "buff_applied"
    BUFF_EXPIRED = "buff_expired"
    ABNORMAL_APPLIED = "abnormal_applied"
    ABNORMAL_ENDED = "abnormal_ended"
    SKILL_CAST = "skill_cast"
    SKILL_FINISH = "skill_finish"
    ATTACK = "attack"
    LIFE_POINT_LOST = "life_point_lost"
    EP_BURST = "ep_burst"
    BATTLE_END = "battle_end"


class EventBus:
    def __init__(self):
        self._subs = {}
        self.log = []

    def subscribe(self, type_, handler):
        self._subs.setdefault(type_, []).append(handler)

    def emit(self, tick, type_, data=None):
        ev = Event(tick, type_, data)
        self.log.append(ev)
        for h in self._subs.get(type_, ()):
            h(ev)
        return ev

    def snapshot_events(self, since_seq=0):
        return [e.to_dict() for e in self.log if e.seq > since_seq]
