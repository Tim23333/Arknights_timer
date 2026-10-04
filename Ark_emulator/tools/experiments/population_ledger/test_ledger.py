"""Owned tokens and registered actors never inflate native wave population."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from tools.campaign_population_ledger import population


def test_native_enemy_owned_hostile_player_token_and_registered_distinct():
    def unit(name,tags):return {'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':10,'move_speed':0}},'resources':{'hp':{'initial':10,'capacity':10}},'spatial':{}}}
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[unit('wave',['enemy']),unit('summon',['enemy']),unit('host',['player']),unit('token',['player','token']),unit('npc',['player'])],
       'scenarioDraft':{'id':'scene/ledger','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'objectives':{},'initialEntities':[
           {'definition':'unit/host','instanceAlias':'host','position':{'row':0,'col':0}},
           {'definition':'unit/npc','registration_key':'native-npc','active':False,'position':{'row':0,'col':1}}],
           'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/wave','position':{'row':0,'col':2}}}]}]}]}}}
    p['entities'][2]['dependencies']=['unit/token','unit/summon']
    s=Engine.create(Compiler().compile(p));s.advance(1)
    # Isolated diagnostic actor creation; no command-replay proof claimed.
    s.ctx.lifecycle.create('unit/token',{'row':0,'col':0},owner='host')
    s.ctx.lifecycle.create('unit/summon',{'row':0,'col':3},owner='host')
    before=s.checkpoint();ledger=population(s)
    assert ledger['counts']['wave_enemies']==1 and ledger['counts']['non_wave_enemies']==1
    assert ledger['counts']['registered_predefines']==1 and ledger['counts']['player_owned']==1
    assert ledger['wave_births_by_definition']=={'unit/wave':1}
    assert ledger['non_wave_births_by_definition']=={'unit/summon':1}
    assert s.checkpoint()==before
