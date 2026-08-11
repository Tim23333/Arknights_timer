"""Ark_emulator - data-driven Arknights battle simulator framework.

Core design: fixed 30Hz logic ticks (GlobalConsts.TIME_ROUGH_LOGIC_RATE=30),
frame-driven simulation of enemies, operators, map, waves, skills and buffs.
All mechanics are implemented from the reverse-engineered data/docs under
ark_parser/enemy (00-11 docs). Mechanics marked TODO/INFERRED need further
calibration (see README.md).
"""

__version__ = "0.1.0"

_LAZY = {}


def __getattr__(name):
    if name == "Simulator":
        from . import api
        return api.Simulator
    raise AttributeError(name)
