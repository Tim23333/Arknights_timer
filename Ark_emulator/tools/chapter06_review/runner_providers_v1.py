"""Frozen explicit C6 content registry entry for full-process runner."""
from tools.chapter06.cold.policies import providers as cold
from tools.chapter06_npcs.providers_v2 import providers as npcs


def providers():
    return {**cold(),**npcs()}
