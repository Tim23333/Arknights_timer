"""Native visible null alias and stock15 stay exact in both source stages."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from tools.chapter07_join.predefines_profile_v1 import profile,declared_cards,MINE

ROOT=Path(__file__).resolve().parents[2]


def source(stage):
    p=json.loads((ROOT/'packages/campaign/chapter07_plans/source.plan.json').read_bytes())
    s=json.loads((ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json').read_bytes())
    return p['stages'][stage]['native_document'],s['stages'][stage]['native_predefines']


def test_717_two_actual_aliases_and_no_cards():
    n,pre=source('level_main_07-15');p=profile(n,pre)
    assert [r['instanceAlias'] for r in p['initial_entities']]==['trap_011_ore#1','trap_011_ore#2']
    assert not p['card_bindings'] and not declared_cards(p)


def test_718_null_alias_kept_and_exact_mine_cardstock15():
    n,pre=source('level_main_07-16');p=profile(n,pre)
    assert len(p['initial_entities'])==1 and 'instanceAlias' not in p['initial_entities'][0]
    assert p['initial_entities'][0]['parameters']['native_instance']['alias'] is None
    assert p['resources']=={'stock_ch7_mine':{'initial':15,'capacity':15}}
    assert declared_cards(p)==[MINE] and p['card_bindings'][0]['native_card']==pre['tokenCards'][0]


@pytest.mark.parametrize('field,value',[('hidden',1),('initialCnt',True),('skillIndex',-1)])
def test_native_card_provenance_mutations_rejected(field,value):
    n,pre=source('level_main_07-16');bad=deepcopy(n)
    bad['predefines']['tokenCards'][0][field]=value
    with pytest.raises(ValueError):profile(bad,pre)
