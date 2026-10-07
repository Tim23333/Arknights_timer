"""Read-only source clock declarations and existing explicit m26 policy."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter0_source_numeric_peer_v1/clock.source.review.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    src=ROOT/'packages/campaign/chapter0_source_prepare/enemies.native.v1.json';source=json.loads(src.read_bytes());rows=[]
    for vid,v in source['variants'].items():
        node=v['modes'][0]['nodes']['_combat'];raw=node['raw'];assert raw['_timeMode']==0
        maximum=raw['_maxAnimScale'];profile=lambda ratio:max(.1,min(ratio,maximum) if maximum>0 else ratio)
        rows.append({'variant':vid,'native_class':node['native_class'],'raw_clock_fields':{k:raw[k] for k in ('_timeMode','_maxAnimScale','_preDelay','_escapeTime','_waitForAttackEvent','_selectTargetTiming','_affectedBySlowDown')},
          'reference_divisor_at_ASPD_1_25':profile(1.25),'reference_divisor_at_ASPD_0_75':profile(.75),'native_animation_binding':node['animation_binding']})
    files=[ROOT.parent/'Ark_data/dump.cs',ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs',ROOT/'tools/build_campaign_attack_talents.py'];facts=[]
    needles=['FROM_ATTACK_SPEED = 0','FROM_ANIMATION = 1','SPECIFIED = 2','LOAD_FROM_BLACKBOARD = 3','MIN_ANIM_SCALE = 0.1','ApplyAttackTime(FP','GetDuration()','UpdatePlaybackSpeed(AbilityStandard.UpdatePlaybackSpeedTiming','profile\':\'from_attack_speed_divisor_model_v1','inputs.timing_parameters.seconds / max(params.minimum,min(inputs.attributes.attack_speed_ratio,params.maximum)']
    for path in files:
        lines=path.read_text(encoding='utf8').splitlines();hits=[{'line':i+1,'text':line.strip()} for i,line in enumerate(lines) if any(n in line for n in needles)]
        facts.append({'path':str(path),'sha256':sha(path),'declaration_evidence':hits})
    result={'schema':'ark-sim/chapter0-source-clock-review/v1','source_sha256':sha(src),'files':facts,'variants':rows,
      'conclusion':'All seven MeleeAttack nodes declare FROM_ATTACK_SPEED=0. Native maxAnimScale is six 1.0 and wteeth float32 approximately1.1; not blanket divisor1.25. Existing m26 models use clamp(ASPD ratio,min.1,max positive source limit).',
      'proposed_replaceable_policy':'Hit and full animation declared seconds divided by max(.1,min(attack_speed_ratio,maxAnimScale) if maxAnimScale>0 else attack_speed_ratio), time.quantize ceil. Independent base attack interval divides by speed without animation cap.',
      'source_supported':'Enum names, exact serialized clock parameters, exact authored animation frames, slowdown enabled, public method declarations.',
      'unrecovered':'Native ApplyAttackTime/GetDuration/UpdatePlaybackSpeed method bodies and relation of source slowDown to ASPD modifier; mid-cast update timing, selectTargetTiming=0 enum/cancellation semantics require distinct audit.',
      'native_formula_confirmed':False,'m26_client_formula_verified':False,'old_v1_unchanged':True,'runtime_started':False,'whole_stage':False,'reviewer_sha256':sha(Path(__file__))}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'report_sha256':sha(OUT),'melee':7,'native_formula_confirmed':False}))
if __name__=='__main__':main()
