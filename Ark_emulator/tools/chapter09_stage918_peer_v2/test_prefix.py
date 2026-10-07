from tools.chapter09_stage918_peer_v2.audit import *
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create():
 package=json.loads(PACKAGE.read_bytes());program=Compiler(providers=REG).compile(package);assert len(program.definitions)>=308;s=Engine.create(program,providers=REG,seed=program.scenario['seed'])
 for command in json.loads(COMMANDS.read_bytes()):
  command=dict(command);at=command.pop('at');s.submit(command,at=at)
 return s

def test_public_actual_plan_firstdeploy_card_to150_two_CP_head_full():
 a=create();a.advance(150);b=create();pins=[];LOG.mkdir(parents=True,exist_ok=True)
 for t in [37,142]:
  b.advance(t-b.session.time);path=LOG/('public_prefix_'+str(t)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append({'path':str(path),'sha256':pin});b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(150-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot()
 outcomes=[thaw(e) for e in a.session.events if e['type'] in ['command.accepted','command.rejected']];assert [(e['time'],e['type']) for e in outcomes]==[(0,'command.accepted'),(120,'command.accepted')];assert outcomes[0]['payload']['action']['entity']=='unit/char_151_myrtle';assert outcomes[1]['payload']['action']['entity']=='unit/ch9/demolition/body';assert a.ctx.resources.current('c9_myrtle','hp')==1565;assert a.ctx.resources.current('c9_device1','hp')==100;assert a.ctx.resources.current('system/battle','stock_ch9_demolition')==1;assert a.ctx.resources.current('system/battle','life')==99999;registry=a.ctx.state()['predefined_registry'];assert len([k for k in registry if k.startswith(STAGE+'/tokenInsts/')])==3
 assert a.ctx.get('c9_device1',('runtime','casts'));assert not a.ctx.state()['finished'];assert guard()==START;REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'public150.actual.json').write_text(json.dumps({'core':CORE,'actual_exit':0,'actual_full_CPP_head_equal':True,'input_sha':sha(PACKAGE),'commands_sha':sha(COMMANDS),'end_tick':150,'all42_real_public_submissions':True,'actual_outcomes':outcomes,'CPs':pins,'complete_state_jobs_RNG_events_cache_context_value_cause':True,'final_checkpoint_digest':digest(a.checkpoint()),'world_native_aliases_preserved':True,'native_HP_unchanged':True,'device_cast_pending155':True,'whole_stage':False},indent=2),encoding='utf8')


def test_changed_complete_Buffmap_cannot_restore_original_actual_prefix_CPP():
 path=LOG/'public_prefix_142.checkpoint.json';receipt=json.loads((REPORT/'public150.actual.json').read_bytes());pin=next(p['sha256'] for p in receipt['CPs'] if p['path']==str(path));cp=load_bound(path,pin);bad=json.loads(PACKAGE.read_bytes());rule=next(d for d in bad['definitions'] if d['id']=='rule/ch9/demolition/push');removed=rule['parameters']['status_definitions'].pop('buff/ch9/pillar/deadlike');program=Compiler(providers=REG).compile(bad)
 with pytest.raises(ValueError) as failure:Engine.restore(program,deepcopy(cp),providers=REG)
 assert 'fingerprint' in str(failure.value).lower();assert cp['attribute_cache']==load_bound(path,pin)['attribute_cache'];(REPORT/'changed_map_CPP.reject.json').write_text(json.dumps({'core':CORE,'actual_rejected':True,'reason':str(failure.value),'removed_definition':'buff/ch9/pillar/deadlike','checkpoint_bytes_sha':pin,'natural_cache_not_deleted_or_altered':True,'scope':'changed rule map belongs to a different program identity; authenticated actual prefix checkpoint refuses it','does_not_claim_missing_map_runtime_shot_covered_by_this_prefix':True},indent=2),encoding='utf8');assert guard()==START
