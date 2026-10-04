"""Compose source NPC providers explicitly for the current content revision."""
from tools.chapter06_npcs.huang_v6_policy import providers as huang
from tools.chapter06_npcs.amiya_policy import providers as amiya


def providers():
    return {**amiya(),**huang()}
