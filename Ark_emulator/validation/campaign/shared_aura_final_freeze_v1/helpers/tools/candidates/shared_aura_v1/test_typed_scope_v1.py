"""Exact typed target gates remain active inside authenticated waiting Aura selection."""
import sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_shared_aura_v8_candidate'));sys.path.insert(1,str(ROOT))
from tools.candidates.shared_aura_v1.test_shared_guarded_v9 import waiting_package,children
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
def make():
 p=waiting_package();cfg={'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':0,'_checkUnitType':0,'_targetSide':1,'_targetCategory':1,'_targetMotion':3};p['rules'].append({'id':'rule/peer/typed','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}});p['selectors'][0]['region']={'type':'radius','radius':3};p['selectors'][0]['eligibility']={'rule':'rule/peer/typed','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}};p['selectors'].append({**deepcopy(p['selectors'][0]),'id':'selector/peer/wrong'});p['scenarioDraft']['dependencies'].append('selector/peer/wrong');s=Engine.create(Compiler().compile(p));s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100});return s
def parent(s):return next(i for i in s.ctx.entity('parent1')['components']['buffs']['instances'] if i['definition'].endswith('/marker'))['id']
def test_typed_general_select_rejects_inactive_but_actual_aura_can_select():
 s=make();uid=parent(s);assert s.ctx.spatial.select('parent1','selector/peer/receiver')==[];assert s.ctx.spatial.select('parent1','selector/peer/receiver',aura_parent=uid)==[s.session.world.resolve('receiver')]
@pytest.mark.parametrize('value',[True,1,{},'not_real_parent'])
def test_forged_or_bad_parent_uid_no_waiting_scope(value):
 s=make()
 with pytest.raises(ValueError):s.ctx.spatial.select('parent1','selector/peer/receiver',aura_parent=value)
def test_real_parent_other_selector_cannot_borrow_aura_scope():
 s=make()
 with pytest.raises(ValueError):s.ctx.spatial.select('parent1','selector/peer/wrong',aura_parent=parent(s))
@pytest.mark.parametrize('field,value',[('target_free',True),('camouflage',True),('side',0),('category',4)])
def test_typed_target_gate_still_rejects_and_releases_child(field,value):
 s=make();uid=parent(s);s.ctx.set('receiver',('selection_state',field),value);assert s.ctx.spatial.select('parent1','selector/peer/receiver',aura_parent=uid)==[];s.ctx.buffs.reconcile();assert not children(s)
def test_waiting_source_hidden_and_target_range_still_checked():
 s=make();uid=parent(s);s.ctx.set('receiver',('spatial','position'),{'row':0,'col':7});assert s.ctx.spatial.select('parent1','selector/peer/receiver',aura_parent=uid)==[]
