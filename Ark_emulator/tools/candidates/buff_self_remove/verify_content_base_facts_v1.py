"""Source-independent typed occupancy query stays pure and exposes native NPCs."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.tile_targets import query
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    definitions=[];initial=[]
    for name,side,mask,col in [('source',1,2,0),('npc',0,1,1),('opponent_char',1,1,2),('token',0,4,3),('mixed_char',0,5,4)]:
        ident='unit/tilefacts/'+name
        definitions.append({'id':ident,'kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':10}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},
            'selection_state':{'side':side,'unit_type':mask,'category':1,'motion':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
        initial.append({'definition':ident,'instanceAlias':name,'position':{'row':0,'col':col}})
    p={'schemaVersion':2,'definitions':definitions,'scenarioDraft':{'id':'scene/tilefacts','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'initialEntities':initial,'objectives':{}}}
    s=Engine.create(Compiler().compile(p),seed=61794)
    spec={'eligibility_expression':'[params.side,params.type_bit] not in inputs.occupied_side_unit_type_bits',
        'parameters':{'side':0,'type_bit':1},'limit':3,'selection':'row_major','stream':None}
    before=s.checkpoint();cells=query(s.ctx,'source',spec);assert s.checkpoint()==before
    assert cells==[{'row':0,'col':0},{'row':0,'col':2},{'row':0,'col':3}],cells
    out=ROOT/'validation/campaign/content_base_v1/facts';out.mkdir(exist_ok=False)
    cp=out/'query_boundary.json';pin=write_ordered(cp,before);r=Engine.restore(s.program,load_bound(cp,pin));r.session.advance(1);s.session.advance(1)
    assert query(r.ctx,'source',spec)==cells and s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cells':cells,
        'friendly_npc_without_deployable_excluded':True,'same_type_other_side_and_token_retained':True,'mixed_mask_bit_projection':True,
        'query_no_world_events_scheduler_RNG_changes':True,'checkpoint_sha':pin,'head_and_restore_equal':True,
        'scope':'Generic actual typed occupancy projection. Source TileSelector filter/body policy and Boss content remain separate.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
