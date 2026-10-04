import json,hashlib,argparse
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(packet='two_full_packets_model',attachment='fixed'):
 if packet not in {'two_full_packets_model','first_signal_only_model'} or attachment not in {'fixed','follow'}:raise ValueError('explicit profile unsupported')
 source=ROOT/'packages/campaign/chapter01_models/w_combat'/('model.json' if packet=='two_full_packets_model' else 'first_signal.model.json');sourcepin='4b647811d8808130970ac85b8a068b4623feb2e1e4fa68dca61d87cccea0df9a' if packet=='two_full_packets_model' else '43fbc5e22aca3230e0d5cbff1d13862239620d4238a30d3c57b0fa65b8873896'
 assert sha(source)==sourcepin
 p=json.loads(source.read_bytes());audit=json.loads((OUT/'source.reference.json').read_bytes());assert audit['passed'];p['manifest']['id']='package/chapter01/projectile-lifecycle';p['status']='executable_declared_projectile_profile_client_pending'
 p['rules']+= [{'id':'rule/projectile/trajectory','kind':'calculation_rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}}, {'id':'rule/projectile/collision','kind':'calculation_rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
 def definition(name,mode,life,attached,stop,invalid):
  return {'id':'projectile/chapter01_w/'+name,'kind':'projectile','motion':{'rule':'rule/projectile/trajectory','parameters':{'mode':mode,'speed':5,'raise_height':.30000001192092896,'height_threshold':1.2999999523162842}},'collision':{'rule':'rule/projectile/collision','parameters':{'enabled':not attached,'radius':0}},'lifetime_seconds':life,'max_hits':1,'can_hit_same_target':False,'stop_after_max':stop,'stop_after_first':False,'attach_at_launch':attached,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':invalid,'target_hidden':invalid,'finish_on_reach':not attached,'hit_on_reach':not attached,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[], 'metadata':{'client_body_calibrated':False,'source_attack_component_closure':True}}
 p['projectiles']=[definition('normal','homing',10,False,True,'cancel'),definition('c4',attachment,3.2,True,False,'retain_position')]
 for a in p['abilities']:
  if a['id'].startswith('ability/chapter01_w_normal_'):
   a['parameters'].pop('projectile_speed',None)
   for item in a['timeline']:item['effect']['projectile_definition']='projectile/chapter01_w/normal'
  elif a['id'].startswith('ability/chapter01_w_c4_'):
   a.setdefault('parameters',{})['wait_for_projectiles']=True
   for item in a['timeline']:
    item['at_seconds']=.6;item['effect']['projectile_definition']='projectile/chapter01_w/c4'
    for e in item['effect'].get('effects',[]):e['read_mode']={'source_attributes':'at_hit'}
 p['manifest'].setdefault('metadata',{})['projectile_lifecycle_profile']={'packet_profile':packet,'attachment':attachment,'clock':'authored_30Hz_source_float_snap_model','trajectory':'planar-homing/swept-trace-point/visual-parabola-model','C4_radius2_5':'declared area interpretation of range_radius; native blast shape unproven','source_audit_sha256':sha(OUT/'source.reference.json'),'old_W_package_sha256':sourcepin,'old_source_body_unknown':True,'no_fullBoss_or_stage_receipt':True}
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 for name,packet,attach in [('model.json','two_full_packets_model','fixed'),('follow.model.json','two_full_packets_model','follow'),('first_signal.model.json','first_signal_only_model','fixed')]:
  value=build(packet,attach);text=json.dumps(value,ensure_ascii=False,indent=2)+'\n';path=OUT/name
  if args.check:assert path.read_text(encoding='utf8')==text
  else:path.write_text(text,encoding='utf8',newline='\n')
 print(json.dumps({'models':3,'check':args.check}))
