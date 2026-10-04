"""Public terrain changes affect pure eligibility through actual grid operands."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_target_tile_facts_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def eligible(inputs,params,context):
    tile=inputs['candidate_spatial_tile']['tile'];accepted=bool(tile['buildableType']&2)
    return {'accepted':accepted,'reason':'actual_tile_mask'}


def main():
    providers={**BUILTIN_PROVIDERS,'probe/actual_tile':{'callable':eligible,'version':'1'}}
    cfg={k:False for k in ['_ignoreTargetFree','_onlyIgnoreSomeOfTargetFreeCase','_excludeSomeAbnormalFlags','_needProfessionMask','_ignoreAllyTargetFree','_ignoreHealFree','_ignoreMotionMode','_forceIgnoreCamouflage','_checkUnitType']}
    cfg.update(_targetSide=2,_targetCategory=1,_targetMotion=1)
    selector={'id':'selector/tile/probe','kind':'selector','region':{'type':'all'},'filters':[{'tag':'candidate'},{'state':'alive'}],
        'eligibility':{'rule':'rule/tile/probe','include_candidate_tile':True,'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULT_STATE}}}
    p={'schemaVersion':2,'manifest':{'id':'package/tile/probe','requires':['preset/ark_standard']},
       'rules':[{'id':'rule/tile/probe','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'probe/actual_tile'}}],
       'selectors':[selector],'entities':[],'abilities':[{'id':'ability/tile/change','kind':'ability','activation':{'mode':'manual','on_start':[{
           'op':'apply_terrain_overlay','target':'self','parameters':{'key':'changed_actual_cell','priority':2,'position':{'row':0,'col':1},'values':{'buildableType':1},'preserve':[]}}]},'timeline':[]}],
       'scenarioDraft':{'id':'scene/tile/probe','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3,'tiles':[
           {'tileKey':'tile_road','buildableType':1,'passableMask':1},{'tileKey':'tile_wall','buildableType':2,'passableMask':2},{'tileKey':'tile_road','buildableType':1,'passableMask':1}]},'objectives':{},'initialEntities':[]}}
    for name,col,tags in [('source',0,[]),('high',1,['candidate']),('far_ground',2,['candidate'])]:
        unit={'id':'unit/tile/'+name,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':100,'atk':10}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/tile/change'] if name=='source' else [],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
        p['entities'].append(unit);p['scenarioDraft']['initialEntities'].append({'definition':unit['id'],'instanceAlias':name,'position':{'row':0,'col':col}})
    p['scenarioDraft']['dependencies']=['selector/tile/probe']
    s=Engine.create(Compiler(providers=providers).compile(p),seed=7181,providers=providers);compiled=s.program.definitions[selector['id']]
    before=s.checkpoint();assert s.ctx.spatial.qualifies('source','high',compiled) and not s.ctx.spatial.qualifies('source','far_ground',compiled);assert s.checkpoint()==before
    out=ROOT/'validation/campaign/target_tile_facts_v1/probe';out.mkdir(exist_ok=False);s.submit({'action':'skill','source':'source','ability':'ability/tile/change'},at=2)
    s.advance(1);cp=out/'before_overlay.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=providers)
    s.advance(3);r.advance(3);assert not s.ctx.spatial.qualifies('source','high',compiled)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay(),providers=providers).checkpoint()
    p2=json.loads(json.dumps(p));p2['selectors'][0]['eligibility']['include_candidate_tile']=1
    try:Compiler(providers=providers).compile(p2)
    except ValueError:pass
    else:raise AssertionError('Bool opt-in accepted int1')
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'actual_high_terrain_only':True,'public_overlay_rechecked':True,'strict_bool_opt_in':True,'pure_query_unchanged':True,'checkpoint_sha':pin,'head_and_restore_equal':True,'scope':'Generic opt-in projected actual terrain facts. Source-specific Patriot masks/camouflage/hate sorting require separate content.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
