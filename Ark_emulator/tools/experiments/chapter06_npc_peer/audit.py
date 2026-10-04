import json,hashlib
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def read(p):return json.loads(p.read_bytes())
def audit():
 source=read(ROOT/'packages/campaign/chapter06_predefines/source.reference.json');inputs=read(ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json');records=source['stages']['level_main_06-15']['instances'];result=[]
 for row in inputs['records']:
  original=next(r for r in records if r['raw_native']['inst']['characterKey']==row['character_id']);raw=original['raw_native'];inst=raw['inst'];assert raw==row['native_instance']
  assert inst['phase']=='PHASE_2' and inst['level']==25 and type(inst['favorPoint']) is int and inst['favorPoint']==0 and type(inst['potentialRank']) is int and inst['potentialRank']==0 and raw['skillIndex']==-1 and row['selected_skill'] is None
  frames=original['raw_character']['phases'][2]['attributesKeyFrames'];favor=original['raw_character']['favorKeyFrames'];actual={}
  for key in ['maxHp','atk','def']:
   lo,hi=frames[0],frames[-1];b=Fraction(str(lo['data'][key]))+(Fraction(24,hi['level']-lo['level']))*(Fraction(str(hi['data'][key]))-Fraction(str(lo['data'][key])));b+=Fraction(str(favor[0]['data'][key]));value=(b.numerator*2+b.denominator)//(2*b.denominator);assert value==row['stats'][key];actual[key]={'fraction':[b.numerator,b.denominator],'half_away_value':value}
  result.append({'npc':row['character_id'],'native_instance':raw,'independent_stat_math':actual})
 npc=source['prefabs']['char_367_swllow'];selectors=[r for r in npc['components'].values() if r['native_class']=='SecondaryFilterAdvancedSelector'];cfg=selectors[0]['raw'];assert cfg['_targetMotion']==3 and cfg['_ignoreTargetFree']==0 and cfg['_forceIgnoreCamouflage']==0
 normal=next(r for r in inputs['records'] if r['character_id']=='char_367_swllow');talent=normal['selected_talents'][0]['candidate'];bb={p['key']:p['value'] for p in talent['blackboard']};assert bb=={'attack_speed':6.0,'prob':.15,'atk_scale':1.5}
 bson=source['bson_templates']['templates']['critical_atkscale']['parsed']['eventToActions']['ON_CALCULATE_DAMAGE'];assert ['Dice' in bson[0]['$type'],'AtkScaleUp' in bson[1]['$type']]==[True,True]
 return {'npc_input_rows':result,'swllow_source_selector':cfg,'source_talent':talent,'source_bson':bson,'normal_attack_raw':normal['normal_attack_source']['raw'],'normal_animation':normal['normal_animation'],'timing_policy':'begin5/OnAttack2 isverified animation data;initialonly cooldown andnormalizedAS conversion/coroutine restart relation remain reference,notnativeprecisewall-clock claim','SP_policy':'No selectedskill means no fabricatedcapacity/skill. OtherNPC futuretalentSP consumers notaccepted bythisSwllowconsumer review.'}
