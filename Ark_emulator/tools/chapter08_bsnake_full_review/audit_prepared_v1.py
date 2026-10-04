"""Read actual prepared source definitions and the real waiting disk checkpoint."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'validation/campaign/chapter08_bsnake_full_input_v2'
ACT=ROOT/'validation/campaign/chapter08_bsnake_full_actual_v1'
OUT=ROOT/'validation/campaign/chapter08_bsnake_full_prepared_audit_v1';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
p=load(BASE/'input.json');ds={d['id']:d for d in p['definitions']}
cp=load(ACT/'waiting200.checkpoint.json');events=cp['kernel']['events']['records']
entities={e['id']:e for e in cp['kernel']['world']['entities']}
assert entities[20]['components']['resources']['hp']['current']==0
timeline=entities[1]['components']['state']['timeline']
assert timeline['members']['20']['wave']==1
assert [(e['time'],e['payload']['from_wave'],e['payload']['to_wave']) for e in events if e['type']=='timeline.source_transferred']==[(117,0,1)]
request=next(e for e in events if e['type']=='timeline.finish_requested')
assert request['time']==57 and request['payload']['parameters']['track_source_at_next_wave'] is True
boss=ds[entities[20]['definition_id']]
assert boss['components']['attributes']['base']['max_hp']==50000
assert boss['components']['attributes']['base']['atk']==770
assert len(p['scenarioDraft']['initialEntities'])==18
first_restore=ds['rule/ch8/bsnake/first_restore']
rows=[]
for did,d in ds.items():
 if d['kind']=='ability' and 'bsnake' in did:
  rows.append({'id':did,'activation':d.get('activation'),'initial_cooldown_seconds':d.get('initial_cooldown_seconds'),'recovery':d.get('recovery')})
sources=[ROOT/'packages/campaign/chapter08_consumers/bsnake/four_modes.wave_source.v5.json',ROOT/'packages/campaign/chapter08_consumers/bsnake/source.first_restore.review.v1.json',ROOT/'packages/campaign/chapter08_consumers/flame/module.v4.joint.json',ROOT/'packages/campaign/chapter08_consumers/flame/loop.profile.v3.json']
helper_dirs=['chapter08_bsnake_combat','chapter08_bsnake_skills','chapter08_bsnake','chapter08_buff_lifetime','chapter08_flame_device']
helpers=[x for folder in helper_dirs for x in (ROOT/'tools'/folder).glob('*polic*.py')]+[ROOT/'tools/chapter08_joint_v4/build_summon_hint_v2.py',ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py']
report={'passed':True,'scope':'Prepared source definition inspection and actual public first kill/HP0 tracked transfer only. Whole/source140 rays and future restoration/replay not signed by this audit. Helper/source guards first sampled during the active run, not falsely called run-start guards.','input_sha':sha(BASE/'input.json'),'actual_waiting200_sha':sha(ACT/'waiting200.checkpoint.json'),'source_pins':{str(x):sha(x) for x in sources},'helper_guards_midrun':{str(x):sha(x) for x in helpers},'actual_hp0_transfer':{'at':117,'source':20,'from':0,'to':1},'first_restore_rule':first_restore,'source_ability_clock_fields':rows}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(sha(OUT/'verification.json'))
