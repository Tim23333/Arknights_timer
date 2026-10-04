"""Readonly frozen real trap profiles activated by ordinary boss source branch."""
import json,hashlib
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2.test_module import package,kill
from tools.chapter06_boss.frstar2.build_module import ROOT,SUM,COLD
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
TRAP=ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json'
TRAPID='unit/ch6/predefined/frosts/source_level1'

def test_true_rebirth_branch_two_exact_aliases_real_frozen_trap_cold_qualification_cp_head(tmp_path):
    assert hashlib.sha256(TRAP.read_bytes()).hexdigest()=='2e7e90422198000d401458e33075edc8f649771c39f82d623d553ab4dc6c5206'
    p=package();p['entities']=[e for e in p['entities'] if e['id']!='unit/test/frstar2/branch_witness']
    for row in p['scenarioDraft']['initialEntities']:
        if row['instanceAlias'].startswith('trap_010_frosts'):row['definition']=TRAPID
    # Source-contained branch-only controlled profile: all actual skill values
    # remain in the module; disable unrelated attack/shield/burst scheduling here.
    boss=p['entities'][0]
    for entry in boss['components']['ability_arbitration']['entries']:
        if entry['ability']!=SUM:entry['condition']='False'
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/frstar2/player','instanceAlias':'near','position':{'row':2,'col':7}})
    program=Compiler(providers=providers()).compile(p,packages=[TRAP]);s=Engine.create(program,seed=6217,providers=providers());kill(s,at=5)
    s.session.advance(305)
    assert not s.ctx.active('trap_010_frosts#1') and not s.ctx.active('trap_010_frosts#2')
    cp=tmp_path/'real.traps.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=providers())
    s.session.advance(500);restored.session.advance(500)
    assert s.ctx.active('trap_010_frosts#1') and s.ctx.active('trap_010_frosts#2')
    acts=[e for e in s.session.events if e['type']=='entity.activated'];assert len(acts)==2
    assert len([e for e in s.session.events if e['type']=='branch.phase_started'])==1
    near=s.ctx.spatial.selection_state('near',DEFAULT_STATE)['abnormal_flags'];assert 23 in near
    cold=next(i for i in s.ctx.get('near',('buffs','instances'),[]) if i['definition']=='buff/ch6/cold/e2c_cold')
    assert cold['expires_at']-cold['started_at']==300
    assert s.snapshot()==restored.snapshot()==replay(program,s.export_replay(),providers=providers()).snapshot()
