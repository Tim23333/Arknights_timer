"""New content versions consume native affectedBySlowDown1/timeMode0; old bytes kept."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
MELEE=ROOT/'packages/campaign/chapter06_units/melee.model.json'
MAGE=ROOT/'packages/campaign/chapter06_units/snmage/model.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def build(path,expected):
    if sha(path)!=expected:raise ValueError('Frozen original module differs')
    p=json.loads(path.read_bytes());metadata=p['manifest']['metadata'];p['manifest']['id']+='/windup_v2'
    metadata['source_locks'][str(path.relative_to(ROOT))]=expected
    metadata['windup_v2_builder_sha256']=sha(Path(__file__))
    metadata['windup_v2_policy']={'formula':'seconds / max(effective attack_speed_ratio,.01), then existing ceil time.quantize','min_speed':.01,'classification':'explicit replaceable timing expression; native affectedBySlowDown1/timeMode0 require actual scaling','native_max_anim_scale':'Preserved per node; graphic clamp relationship to event timing/body is unresolved. Reference policy applies min.01 normalized timing, does not assert a native maximum damage-event clamp','scope':'Actual ASPD1/.7 clocks; source module and source cold bytes unchanged','formal_approved':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    bindings=[]
    for ability in p['abilities']:
        if path==MELEE:node=ability['metadata']['source_combat']
        else:node=metadata['source_binding']['unique_nodes']['cold_attack' if ability['id'].endswith('/coldattack') else 'normal_attack']
        raw=node['raw']
        if (raw['_affectedBySlowDown'],raw['_timeMode'],raw['_waitForAttackEvent'])!=(1,0,1):raise ValueError('Exact timing source operands differ')
        ident='rule/'+ability['id']+'/source_windup_v2'
        p['rules'].append({'id':ident,'kind':'calculation_rule','contract':'ability.windup','parameters':{'minimum_speed':.01,'native_max_anim_scale':raw['_maxAnimScale']},'implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'},'metadata':{'native_node_path_id':node.get('path_id'),'native_timing_fields':{k:raw[k] for k in ('_affectedBySlowDown','_timeMode','_waitForAttackEvent','_maxAnimScale','_preDelay','_animKey')},'native_body_verified':False,'reference_replaceable':True}})
        ability.setdefault('rules',{})['ability.windup']=ident
        bindings.append({'ability':ability['id'],'windup_rule':ident,'native_path_id':node.get('path_id'),'native_timing_fields':{k:raw[k] for k in ('_affectedBySlowDown','_timeMode','_maxAnimScale','_animKey')},'native_timeline':deepcopy(ability['timeline'])})
    metadata['windup_v2_bindings']=bindings
    return p
if __name__=='__main__':
    for path,pin,out in [(MELEE,'7417d5342a7affec7d872715bb810c01dc65422dcd30c41064d33ec33a776f31',ROOT/'packages/campaign/chapter06_units/melee_v2/model.json'),(MAGE,'c9c5d932a1651904b1626fc428d8436ba97d57e795dd29cb81f3ffd892ed8344',ROOT/'packages/campaign/chapter06_units/snmage_v2/model.json')]:
        write(out,build(path,pin));print(json.dumps({'module':str(out),'sha256':sha(out)}))
