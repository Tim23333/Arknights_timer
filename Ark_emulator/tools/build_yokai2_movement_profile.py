"""New declared movement policy, retaining frozen stationary-target evidence."""
import json,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json';PIN='4d9d07839243f1d2a7d7852f8952415f6971496473483765148a2def9ec10306';SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json';SOURCEPIN='97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492';OUT=ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.yokai2_move.reference_module.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 assert sha(BASE)==PIN and sha(SOURCE)==SOURCEPIN;p=json.loads(BASE.read_bytes());d=json.loads(SOURCE.read_bytes());v=d['variants']['enemy_1005_yokai_2@0/dbec03902e7c8432'];attack=v['modes'][0]['nodes']['_attack'];assert attack['raw']['_endAnimKey']=='Move' and [e['frame'] for e in attack['animation_binding']['events'] if e['name']=='OnAttack']==[8]
 b=next(x for x in p['definitions'] if x['id']=='behavior/chapter02/yokai_2');profile=b['decision']['profiles'][0];assert profile['parameters']['stop_on_target'] is True and profile['parameters']['stop_cast_groups']==['attack'];profile['parameters']['stop_on_target']=False
 meta=p['manifest']['metadata'];meta.update(yokai2_movement_builder_sha256=sha(__file__),parent_enemy_module_sha256=PIN,yokai2_movement_policy={'source_variant':v['variant_id'],'source_attack':attack,'source_end_animation':'Move','selected_policy':'move with eligible surviving target except existing automatic cast group; f8 short cast ends then movement resumes','alternative_pending':'continuous movement during attack cast would be a different explicit policy','reference_url':'https://prts.wiki/w/妖怪MKII','checked_date':'2026-10-03','reference_scope':'page confirms flight/ranged/stats/moveMultiplier .5, does not independently state native moving-while-attack permission','source_body_pending':True});meta['source_locks'].update({str(BASE.relative_to(ROOT)):PIN,str(SOURCE.relative_to(ROOT)):SOURCEPIN});p['manifest']['id']+='/yokai2_move_between_casts';return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:assert OUT.read_bytes()==raw
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'sha256':sha(OUT)}))
