"""Explicit full source providers; callable closures fixed and names preserved."""
from tools.chapter07_strength_melee.policies_v2 import providers as strength
from tools.chapter07_predefines.policies_v1 import providers as ore
from tools.chapter07_boss.policies_v2 import providers as boss
from tools.chapter07_ranged_consumers.policies_v1 import providers as ranged
from tools.chapter07_ranged_consumers.mortar_box_v2 import mortar_box

def providers():
 registry={}
 for source in (strength(),ore(),boss(),ranged()):
  for name,value in source.items():
   if name in registry and registry[name]!=value:raise ValueError('Conflicting provider '+name)
   registry[name]=value
 registry['reference.c7.mortar_box']={'callable':mortar_box,'version':'2'}
 return registry
