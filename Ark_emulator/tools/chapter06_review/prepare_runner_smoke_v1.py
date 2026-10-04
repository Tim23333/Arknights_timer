"""Tiny actual source-provider timeline, not substituted for a campaign stage."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'validation/campaign/chapter06_provider_runner_smoke_v1';out.mkdir(exist_ok=False)
    source=ROOT/'packages/campaign/chapter06_cold/model.json';p=json.loads(source.read_bytes())
    p['entities']=[{'id':'unit/provider_runner/enemy','kind':'entity','tags':['enemy'],'components':{
        'attributes':{'base':{'max_hp':100,'atk':0,'move_speed':3,'one_minus_status_resistance':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    scene={'id':'scene/provider_runner/smoke','ruleset':'ruleset/ark_standard','seed':61791,'map':{'rows':1,'cols':3},
        'objectives':{'type':'waves','life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},
        'metadata':{'runthrough_profile':{'base_life_resource':'life','scope':'One enemy provider runner smoke only'}},
        'dependencies':['rule/ch6/cold/application'],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':0,'post_delay_seconds':0,'max_wait_seconds':-1,
            'fragments':[{'pre_delay_seconds':0,'actions':[{'kind':'spawn','count':1,'managed':True,'blocks_wave':True,'blocks_fragment':False,
                'spawn':{'definition':'unit/provider_runner/enemy','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}}]}]}]}}
    # Use the actual cold application rule ID found in the source module.
    scene['dependencies']=[r['id'] for r in p['rules'] if r['contract']=='buff.application']
    p['scenarioDraft']=scene
    for name,value in [('input.json',p),('commands.json',[])]:
        (out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'input_sha':hashlib.sha256((out/'input.json').read_bytes()).hexdigest()}))


if __name__=='__main__':main()
