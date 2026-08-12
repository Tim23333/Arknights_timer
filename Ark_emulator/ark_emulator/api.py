"""Simulator facade - public entry point for AI analysis.

Usage::

    from ark_emulator import Simulator
    sim = Simulator(level_id="level_main_01-01")
    sim.run(seconds=10)
    snap = sim.snapshot()
    sim.pause(); sim.step(30); sim.resume()
    sim.deploy("char_002_amiya", row=3, col=4, direction=1)
"""

from .loader import DataStore


class Simulator:
    """High-level battle simulation facade.

    Wraps BattleController (battle.py) plus player-facing controls and the
    full-field snapshot API. BattleController is imported lazily so this
    module is importable while the battle layer is still being built.
    """

    def __init__(self, level_id="level_main_01-01", stage_id=None,
                 data_dir=None, squad=None, seed=None, custom_enemies=None,
                 custom_level=None, rune_difficulty=1):
        self._store = DataStore(data_dir) if data_dir else DataStore()
        if stage_id is not None and level_id is None:
            level_id = self._store.stage_to_level(stage_id)
        self.level_id = level_id
        self.seed = seed
        self.squad = squad or []
        self.custom_enemies = custom_enemies or []
        self.custom_level = custom_level
        self.rune_difficulty = int(rune_difficulty or 1)
        self._battle = None

    @property
    def store(self):
        """DataStore (enemy roster, levels, skills) for tooling/editor."""
        return self._store

    # ---- lifecycle ----
    @property
    def battle(self):
        if self._battle is None:
            from .battle import BattleController
            self._battle = BattleController(
                level_id=self.level_id,
                store=self._store,
                seed=self.seed,
                squad=self.squad,
                custom_enemies=self.custom_enemies,
                custom_level=self.custom_level,
                rune_difficulty=self.rune_difficulty,
            )
        return self._battle

    def run(self, seconds=None, ticks=None):
        """Advance the simulation for a wall-clock duration (seconds) or a
        fixed number of ticks. Whichever is given; seconds defaults to 1."""
        if ticks is not None:
            return self.run_ticks(ticks)
        if seconds is None:
            seconds = 1.0
        return self.run_ticks(int(round(seconds * 30)))

    def run_ticks(self, n):
        """Advance exactly n logic ticks (30 ticks = 1 second)."""
        for _ in range(int(n)):
            if self.battle.finished:
                break
            self.battle.tick_once()
        return self.snapshot()

    def tick_once(self):
        self.battle.tick_once()
        return self.snapshot()

    # ---- pause / step / resume ----
    def pause(self):
        self.battle.paused = True

    def resume(self):
        self.battle.paused = False

    def step(self, n=1):
        """Advance n ticks while paused (auto-resumes afterwards)."""
        was_paused = self.battle.paused
        self.battle.paused = False
        try:
            self.run_ticks(n)
        finally:
            self.battle.paused = was_paused
        return self.snapshot()

    # ---- player actions ----
    def deploy(self, char_id, row, col, direction=1, auto_summon=False,
               skill_index=None):
        """Deploy an operator; returns (ok, inst_id or reason).

        auto_summon=True also places the operator's bound summon (e.g.
        Kal'tsit's Mon3tr) on the first free neighbouring tile.
        """
        return self.battle.deploy(char_id, row, col, direction,
                                  auto_summon=auto_summon,
                                  skill_index=skill_index)

    def deploy_summon(self, char_id, row, col, direction=1, owner=None,
                      skill_index=None):
        """Deploy the summon bound to a deployed operator."""
        return self.battle.deploy_summon(char_id, row, col, direction,
                                         owner=owner, skill_index=skill_index)

    def withdraw_token(self, inst_id):
        """Retreat a summon token."""
        return self.battle.withdraw_token(inst_id)

    def withdraw(self, inst_id):
        return self.battle.withdraw(inst_id)

    def deploy_token(self, token_key, row, col, direction=1, owner=None):
        """Deploy a token / summon at a tile."""
        return self.battle.deploy_token(token_key, row, col, direction,
                                        owner=owner)

    def deploy_gained_token(self, token_key, row, col, direction=1,
                            owner=None):
        """Deploy a player-side token gained via a GainToken buff node
        (consumes one inventory count)."""
        return self.battle.deploy_gained_token(token_key, row, col,
                                               direction, owner=owner)

    def activate_skill(self, inst_id, skill_index=0):
        return self.battle.activate_skill(inst_id, skill_index)

    # ---- snapshot ----
    def snapshot(self, since_seq=0):
        """Full-field snapshot: battle state + increment events."""
        return self.battle.snapshot(since_seq=since_seq)

    @property
    def tick(self):
        return self.battle.tick

    @property
    def finished(self):
        return self.battle.finished
