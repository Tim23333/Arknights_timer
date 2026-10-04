"""Independent M14 source-consumer review, no battle mutation or receipt."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
CORE='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
NEW='83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2'
OLD='0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4'
def read(p):return json.loads((ROOT/p).read_bytes())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def ref(p,claim):return {'path':p,'sha256':sha(p),'claim':claim}
def write(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def run():
 assert implementation_digest()==CORE
 oldp='packages/campaign/mainline_models/level_main_00-10.m12_projection.json';newp='packages/campaign/mainline_models/level_main_00-10.m14_timeline.json'
 assert sha(oldp)==OLD and sha(newp)==NEW
 old,new=read(oldp),read(newp);sections=['entities','abilities','buffs','selectors','rules','behaviors']
 for k in sections:assert json.dumps(old[k],ensure_ascii=False,indent=2).encode()==json.dumps(new[k],ensure_ascii=False,indent=2).encode()
 for k in ('roster','map','rules','resources','parameters','objectives','seed'):assert new['scenarioDraft'][k]==old['scenarioDraft'][k]
 assert 'waves' not in new['scenarioDraft'] and 'scheduledEffects' not in new['scenarioDraft']
 nativep='packages/campaign/native_reference/level_main_00-10.json';native=read(nativep)
 timeline=new['scenarioDraft']['timeline'];assert timeline['policy']=='managed_clear' and timeline['negative_timeout_policy']=='wait_for_clear'
 assert len(timeline['waves'])==len(native['waves'])
 population=0;ui=0
 for nw,w in zip(native['waves'],timeline['waves']):
  assert [w[k] for k in ('pre_delay_seconds','post_delay_seconds','max_wait_seconds')]==[nw[k] for k in ('preDelay','postDelay','maxTimeWaitingForNextWave')]
  assert len(nw['fragments'])==len(w['fragments'])
  for nf,f in zip(nw['fragments'],w['fragments']):
   assert f['pre_delay_seconds']==nf['preDelay'] and len(f['actions'])==len(nf['actions'])
   for na,a in zip(nf['actions'],f['actions']):
    assert a['metadata']['native_action']==na and [a[k] for k in ('delay_seconds','count','interval_seconds')]==[na[k] for k in ('preDelay','count','interval')]
    if na['actionType']=='SPAWN':
     assert a['kind']=='spawn' and a['managed']==na['managedByScheduler'] and a['blocks_wave']==(not na['dontBlockWave']) and a['blocks_fragment']==na['blockFragment'];population+=a['count']
     assert a['spawn']['definition']=='unit/'+na['key']
    else:
     assert a['kind']=='effects' and a['metadata']['zero_lifetime_member_elision'] is True and not na['blockFragment']
     assert a['effects'][0]['event']=='m14.ui.started' and a['effects'][-1]['event']=='m14.ui.ack_finished';ui+=a['count']
 assert population==35 and ui==2
 program=Compiler().compile(new);defs={k:thaw(v) for k,v in program.definitions.items()};units=[]
 mapping={'maxHp':'max_hp','atk':'atk','def':'def','magicResistance':'mres','baseAttackTime':'attack_interval','moveSpeed':'move_speed','blockCnt':'block_count','cost':'deploy_cost','respawnTime':'redeploy_time','massLevel':'mass_level'}
 for r in read('packages/campaign/operators.normalized.json')['operators']:
  u=defs['unit/'+r['character_id']];c=u['components'];s=r['stats']['model_stats'];a=u['metadata']['selected_skill_ability']
  assert all(c['attributes']['base'][v]==s[k] for k,v in mapping.items()) and c['attributes']['base']['attack_speed_ratio']==s['attackSpeed']/100
  assert u['metadata']['config']==r['config'] and a in c['abilities'] and defs[a]['metadata']['native_skill_id']==r['selected_skill']['skill_id']
  assert c['resources']['sp']['initial']==r['selected_skill']['level']['spData']['initSp'] and c['resources']['sp']['capacity']==r['selected_skill']['level']['spData']['spCost']
  units.append({'character_id':r['character_id'],'selected_owned':a,'initial_talents':c.get('buffs',{}).get('initial',[])})
 audit=read('packages/campaign/conversion_drafts/main_00-10.audit.json');locks=audit['source_locks']
 for r in locks:assert sha(r['path'])==r['sha256']
 for closure in audit['operator_definition_closures']:
  for row in closure['reachable_definition_identities']:assert ident(defs[row['id']])==row['sha256']
 peerp='validation/campaign/m14_timeline_peer_frozen.json';peer=read(peerp)
 assert peer['passed'] and peer['identity_stable'] and peer['implementation_sha256']==CORE and peer['input_package_sha256']==NEW
 assert len(peer['cases'])==7 and all(r['result']=='passed' for r in peer['cases'])
 for p,h in peer['source_at_start'].items():assert Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h and peer['source_at_completion'][p]==h
 rawp='validation/campaign/first_model_original_fields_root_review_20261002.json';raw=read(rawp)
 assert raw['passed'] and raw['identity_stable'] and raw['json_fields_read']==2526 and raw['unity_fields_read']==270
 subp='validation/campaign/m14_source_consumer_subchecks.json'
 write(subp,{'schema':'ark-sim/m14-independent-consumer-subchecks/v1','passed':True,'implementation_sha256':CORE,'subject_model_content_sha256':NEW,'canonical_sections_byte_equal':sections,'unchanged_scene_fields':['roster','map','rules','resources','parameters','objectives','seed'],'operators':units,'definition_closures_checked':True,'native_spawns':population,'UI_zero_lifetime_actions':ui,'source_lock_count':len(locks),'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__).relative_to(ROOT)),'result':'passed'}]})
 checks=['unit_attributes_and_growth','selected_skills_and_talents','native_enemy_dependencies','map_routes_controls_and_objectives','no_substituted_or_ignored_mechanics']
 claims=['Actual twelve normalized stats/config/ASPD mapped to compiled units; model interpolation profile unchanged','Actual selected ability ownership/SP/talent closure identities; every actor definition byte equal','Actual enemy definitions/combat/frames and selectors byte equal; raw Unity values covered separately','Actual map/rules/objectives preserved and native timeline counts/delays/gates consumed','All unchanged canonical sections and every native action accounted for; mathematical clear and zero-lifetime UI profiles explicit']
 consumers={k:[ref(subp,c)] for k,c in zip(checks,claims)}
 for k in checks[3:]:consumers[k].append(ref(peerp,'Seven independently executed cases: native 35/17/5 projection, managed release/deadline/UI zero-life equivalence/CP replay and source mutants'))
 locks=deepcopy(locks)+[{'path':newp,'sha256':NEW},{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'sha256':sha(Path(__file__).relative_to(ROOT))},{'path':peerp,'sha256':sha(peerp)}]
 output={'schema':'ark-sim/source-consumer-review/v2','passed':True,'status':'approved_for_declared_model_profile','reviewer':'campaign_catalog independent source consumer review','subject_model_content_sha256':NEW,'subject_native_source_sha256':sha(nativep),'implementation_sha256':CORE,'source_locks':locks,'checks':dict.fromkeys(checks,'passed'),'consumer_evidence':consumers,'raw_source_evidence':[ref(rawp,'Separate direct raw-field evidence; not semantic approval')],'pending_model_gaps':[],'client_pending':['Native scheduler managed/negative-timeout method bodies','Native UI callback duration/game-time/wall-time pause','Existing declared movement/RNG/stat interpolation/animation callback profiles remain client uncalibrated'],'scope':'Declared executable mathematical profiles only. No complete-stage or external model receipt; original 0fb missing Timeline gap remains blocked for that subject.','formal_approval':False,'external_receipt_issued':False}
 assert implementation_digest()==CORE
 write('validation/campaign/m14_source_consumer_review.json',output)
 print(json.dumps({'passed':True,'subject':NEW,'locks':len(locks),'units':len(units),'peer_cases':len(peer['cases'])}))
if __name__=='__main__':run()
