import sys,json
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_wave_track_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest
OUT=ROOT/'validation/campaign/chapter08_wave_track_author_v1'
def request(track=True):return {'op':'finish_timeline_wave','target':'source','parameters':{'finish_and_skip':False,'track_source_at_next_wave':track,'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}}
def package(track=True):
 boss={'id':'unit/track/boss','kind':'entity','tags':['enemy','boss'],'components':{'attributes':{'base':{'max_hp':1000}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'rebirth':{'resource':'hp','max_count':1,'delay_seconds':1,'restore_ratio':.5,'restore_rule':'rule/track/restore','retain_buffs':['buff/track/source'],'on_begin':[{'op':'apply_buff','target':'source','buff':'buff/track/source'}]}}}
 enemy=deepcopy(boss);enemy['id']='unit/track/other';enemy['tags']=['enemy'];enemy['components'].pop('rebirth')
 director={'id':'unit/track/director','kind':'entity','tags':['player'],'components':{'spatial':{},'abilities':['ability/track/kill','ability/track/retire']}}
 abilities=[{'id':'ability/track/'+key,'kind':'ability','selector':'selector/track/boss','activation':{'mode':'manual','on_start':[{'op':'instant_kill','parameters':{'cause':'track_public_'+key,'skip_rebirth':key=='retire'}}]},'timeline':[]} for key in ['kill','retire']]
 def spawn(definition,alias,delay=0):return {'kind':'spawn','delay_seconds':delay,'managed':True,'blocks_wave':True,'blocks_fragment':False,'spawn':{'definition':definition,'instanceAlias':alias,'position':{'row':0,'col':1}}}
 return {'schemaVersion':2,'manifest':{'id':'package/track/actual','requires':['preset/ark_standard']},'entities':[boss,enemy,director],'abilities':abilities,'selectors':[{'id':'selector/track/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1}],'rules':[{'id':'rule/track/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}}],'buffs':[{'id':'buff/track/source','kind':'buff','duration_seconds':.1,'on_remove':[request(track)]}],'scenarioDraft':{'id':'scene/track/actual','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'objectives':{},'initialEntities':[{'definition':director['id'],'instanceAlias':'director','position':{'row':0,'col':0}}],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.1,'post_delay_seconds':.1,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':2/30,'actions':[spawn(boss['id'],'boss'),spawn(enemy['id'],'old_other',.5)]}]},{'pre_delay_seconds':5/30,'post_delay_seconds':0,'max_wait_seconds':-1,'fragments':[{'actions':[dict(spawn(enemy['id'],'next_other'),blocks_wave=False)]}]}]}}}
def make(p=None):
 p=p or package();pr=Compiler().compile(p);s=Engine.create(pr,seed=8188);s.submit({'action':'skill','source':'director','ability':'ability/track/kill'},at=7);return pr,s,p
def proof(pr,s,p,name,split,end):
 s.advance(split);d=OUT/name;d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h));s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();(d/'evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8');return s

def test_actualHP0_alive_source_transfers_only_one_after_original_births_delays_CPP15_head():
 pr,s,p=make();s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60);s.advance(24);ref=s.session.world.resolve('boss');assert s.ctx.alive(ref) and not s.ctx.active(ref) and s.ctx.resources.current(ref,'hp')==0;state=s.ctx.state()['timeline'];assert state['members'][str(ref)]['wave']==1;assert state['members'][str(s.session.world.resolve('old_other'))]['wave']==0;assert [(e['time'],e['payload']['from_wave'],e['payload']['to_wave']) for e in s.session.events if e['type']=='timeline.source_transferred']==[(23,0,1)]
 # Fresh CP sits before original remaining birth20 and before membership transfer23.
 pr,s,p=make();s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60);proof(pr,s,p,'HP0_tracking',15,70);births=[e for e in s.session.events if e['type']=='entity.created' and 'enemy' in s.ctx.entity(e['payload']['entity'])['tags']];assert [e['time'] for e in births]==[5,20,28];assert s.ctx.state()['pending_waves']==0 and s.ctx.state()['timeline']['done'];assert [e['time'] for e in s.session.events if e['type']=='timeline.wave_completed']==[20,61];assert not s.ctx.alive('boss') and s.ctx.alive('old_other') and s.ctx.alive('next_other')

@pytest.mark.parametrize('key,value',[('finish_and_skip',True),('track_source_at_next_wave',1),('track_source_wave_delta',True),('track_source_wave_delta',1),('track_all_managed_at_next_wave',True)])
def test_unimplemented_or_badtype_still_reject(key,value):
 p=package();p['buffs'][0]['on_remove'][0]['parameters'][key]=value
 with pytest.raises(Exception):Compiler().compile(p)

def test_same_wave_request_idempotent_no_second_membership_or_wake():
 pr,s,p=make();s.advance(12);before=s.checkpoint();assert s.ctx.timeline.finish_current('boss',request()) is False;assert s.checkpoint()==before
