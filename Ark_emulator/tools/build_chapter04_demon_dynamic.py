"""Single-ability, cast-scheduled dynamic animation profile; explicit consumption phase."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter04_units/demon_profiles/with_pre_only.model.json';PIN='f5103e26b002a788b20997eb0be0d84e429e1e572a55f067624fe28a22b3e8ac';OUT=ROOT/'packages/campaign/chapter04_units/demon_dynamic';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(consume_phase):
 if consume_phase not in ('start','first_hit','finish'):raise ValueError('Explicit first-branch consumption phase required')
 raw=PARENT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen static branch changed')
 p=json.loads(raw);m=p['manifest']['metadata'];m.update(builder_sha256=sha(__file__),branch_policy='first_with_pre_then_no_pre',consume_phase=consume_phase,native_dispatch_pending=True,client_verified=False)
 m['source_locks']['packages/campaign/chapter04_units/demon_profiles/with_pre_only.model.json']=PIN
 m['branch_semantics']={'animation_branch':'0=first branch not consumed; 1=consumed; exact trigger chosen by consume_phase','captured_animation_branch':'copy at cast start before optional start consumption; stored in source_snapshot','first_hit':'first accepted positive HP damage for this ability; missing/dead target does not consume','finish':'actual ability.finished event; interrupted casts do not consume','start':'successfully committed cast start, including later interrupted/missed casts','scheduling':'Both offsets evaluate before on_start; mid-cast branch changes cannot alter already scheduled jobs','clock':'One automatic ability and actor next_attack, native DB interval2 seconds','playback':'Inherited fixed authored clock at native AS100; native speed callback calibration retained'}
 p['manifest']['id']='package/ch4/demon/dynamic/'+consume_phase
 unit=p['entities'][0];res=unit['components']['resources'];res['animation_branch']={'initial':0,'capacity':1};res['captured_animation_branch']={'initial':0,'capacity':1}
 ability=p['abilities'][0];aid=ability['id'];ability['rules']={'ability.windup':'rule/ch4/demon_branch_windup'}
 ability['activation']['on_start']=[{'op':'modify_resource','target':'source','resource':'captured_animation_branch','amount_rule':'rule/ch4/demon_capture_branch'}]
 consume={'op':'modify_resource','target':'source','resource':'animation_branch','value':1}
 if consume_phase=='start':ability['activation']['on_start'].append(consume)
 else:
  event='damage.accepted' if consume_phase=='first_hit' else 'ability.finished'
  condition='inputs.payload.source == context.owner.id and inputs.payload.ability == params.ability_id'
  if consume_phase=='first_hit':condition+=' and inputs.payload.amount > 0'
  ability['events']=[{'event':event,'condition':condition,'parameters':{'ability_id':aid},'effects':[consume]}]
 ability['metadata'].update(branch_policy='first_with_pre_then_no_pre',consume_phase=consume_phase)
 b='context.source.components.resources.animation_branch.current'
 p['rules'].extend([{'id':'rule/ch4/demon_branch_windup','kind':'rule','contract':'ability.windup','parameters':{'repeat_shift_seconds':.4},'implementation':{'type':'expression','expression':f'inputs.timing_parameters.seconds if {b} == 0 else (inputs.timing_parameters.seconds - params.repeat_shift_seconds if {b} == 1 else 1 / 0)'}}, {'id':'rule/ch4/demon_capture_branch','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':b}}])
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 for phase in ('start','first_hit','finish'):
  raw=(json.dumps(build(phase),ensure_ascii=False,indent=2)+'\n').encode();path=OUT/(phase+'.model.json')
  if args.check:
   if path.read_bytes()!=raw:raise ValueError('Dynamic source profile drift')
  else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  print(json.dumps({'phase':phase,'sha256':hashlib.sha256(raw).hexdigest()}))
