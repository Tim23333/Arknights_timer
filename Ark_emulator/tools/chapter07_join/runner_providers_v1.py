"""Explicit fixed source registry for the first native chapter7 source run."""
from tools.chapter07_strength_melee.policies_v2 import providers as strength
from tools.chapter07_predefines.policies_v1 import providers as ore


def providers():return {**strength(),**ore()}
