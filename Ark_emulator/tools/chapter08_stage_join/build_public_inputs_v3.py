"""Life-only99999 and sourcelegal fixed12 rotation, actual outcomes remain pending."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
PARENT=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v5.json'
COMMANDS=ROOT/'scenarios/campaign/chapter08/level_main_08-16/public_plan_v3/commands.json'
OVERLAY=PARENT.with_name('level_main_08-16.native_draft.v5.life99999.v1.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if p.exists():
        assert p.read_bytes()==raw,'Existingfrozen input differs'
        return
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
def build():
    assert sha(PARENT)=='f94e1d9fa30b2d12ddf686aeb84d68c9e9c2c28af48621f9ffe2338476f93a54'
    p=json.loads(PARENT.read_bytes());roster=p['scenarioDraft']['roster'];ops=[]
    deployments=[(0,'151_myrtle',6,7,'up'),(870,'222_bpipe',6,7,'up'),(1350,'128_plosis',5,6,'right'),
        (1830,'010_chen',4,7,'up'),(2310,'107_liskam',3,7,'right'),(2790,'202_demkni',4,8,'left'),
        (3270,'103_angel',5,8,'up'),(3750,'180_amgoat',2,8,'down'),(4230,'003_kalts',5,5,'right'),
        (4710,'358_lisa',2,6,'right'),(5490,'400_weedy',3,8,'left'),(5970,'179_cgbird',5,4,'right')]
    for at,key,row,col,facing in deployments:
        unit='unit/char_'+key;assert unit in roster;terrain=next(d for d in p['definitions'] if d['id']==unit)['components']['deployable']['terrain'];tile=p['scenarioDraft']['map']['tiles'][row*p['scenarioDraft']['map']['cols']+col]
        assert tile['buildableType']==(1 if terrain=='ground' else 2)
        ops.append({'at':at,'action':'deploy','entity':unit,'row':row,'col':col,'facing':facing,'alias':'c8_'+key.split('_',1)[1]})
    for at,key in [(810,'myrtle'),(4650,'bpipe'),(5130,'chen'),(5610,'liskam')]:ops.append({'at':at,'action':'withdraw','source':'c8_'+key})
    skills=[(300,'myrtle','ability/campaign_myrtle_s2'),(2400,'bpipe','ability/campaign_bpipe_s3'),(4500,'kalts','ability/kalts_summon'),
        (4800,'kalts','ability/kalts_host_s3'),(4800,'amgoat','ability/campaign_amgoat_s3'),(5100,'demkni','ability/demkni_s3'),
        (5400,'lisa','ability/lisa_s3'),(5400,'plosis','ability/plosis_s2_first_packet'),(6090,'weedy','ability/campaign_weedy_deploy_cannon'),
        (6150,'weedy','ability/campaign_weedy_s3'),(6540,'cgbird','ability/cgbird_s3'),(6570,'cgbird','ability/support_night_bird')]
    ids={d['id'] for d in p['definitions']}
    for at,key,aid in skills:
        assert aid in ids,aid;op={'at':at,'action':'skill','source':'c8_'+key,'ability':aid}
        if aid=='ability/kalts_summon':op['payload']={'position':{'row':4,'col':9},'facing':'left'}
        if aid=='ability/campaign_weedy_deploy_cannon':op['payload']={'position':{'row':3,'col':9},'facing':'left'}
        if aid=='ability/support_night_bird':op['payload']={'position':{'row':4,'col':10},'facing':'left'}
        ops.append(op)
    ops.sort(key=lambda o:o['at']);assert len(ops)==28
    write(COMMANDS,ops)
    native=deepcopy(p['scenarioDraft']['resources']['life']);p['scenarioDraft']['resources']['life']={'initial':99999,'capacity':99999}
    p['scenarioDraft']['metadata']['runthrough_profile']={'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(roster),'source_births':32,'deploy_capacity':9,
        'public_commands_sha256':sha(COMMANDS),'operator_enemy_HP':'Original exact source module HP','training_deployment_exception':False,'client_verified':False,'accuracy':'Reference-source model; user client feedback pending'}
    p['manifest']['metadata']['goal_base_life_authoring']={'native':native,'selected_initial':99999,'selected_capacity':99999,'only_authoring':'Campaign user base life policy'}
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    validate_native_overlay(p,json.loads(PARENT.read_bytes()),COMMANDS);write(OVERLAY,p)
    return {'parent_sha':sha(PARENT),'overlay_sha':sha(OVERLAY),'commands_sha':sha(COMMANDS),'planned_commands':28,'planned_players':12,'only_base_life':True,'actual_deployments_pending':True,'source_admission_pending':True}
if __name__=='__main__':print(json.dumps(build()))
