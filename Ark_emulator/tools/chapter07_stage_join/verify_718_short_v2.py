import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter07_strength_melee.policies_v2 import providers as strength
from tools.chapter07_predefines.policies_v1 import providers as ore
from tools.chapter07_boss.policies_v2 import providers as boss
from tools.chapter07_ranged_consumers.policies_v1 import providers as ranged
from tools.chapter07_ranged_consumers.mortar_box_v2 import mortar_box
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
REG={**strength(),**ore(),**boss(),**ranged(),'reference.c7.mortar_box':{'callable':mortar_box,'version':'2'}}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000';src=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-16.native_draft.v2.json';p=json.loads(src.read_bytes());program=Compiler(providers=REG).compile(p);s=Engine.create(program,providers=REG,seed=program.scenario['seed']);driver=PublicAckDriver(s);scene=p['scenarioDraft'];tile=next((i,t) for i,t in enumerate(scene['map']['tiles']) if t['buildableType']&1 and t['passableMask']&1);i=tile[0];row=i//scene['map']['cols'];col=i%scene['map']['cols'];command={'action':'deploy','entity':'unit/ch7/predefined/mine/level1','alias':'public_mine','row':row,'col':col,'facing':'up'};s.submit(command,at=100);driver.advance_to(3);out=ROOT/'validation/campaign/chapter07_718_3992_short_v1';out.mkdir(exist_ok=False);cp=out/'story3.json';h=write_ordered(cp,s.checkpoint());side=driver.checkpoint();r=Engine.restore(program,load_bound(cp,h),providers=REG);dr=PublicAckDriver(r,side);driver.advance_to(300);dr.advance_to(300);head=replay(program,s.export_replay(),providers=REG);assert s.checkpoint()==r.checkpoint()==head.checkpoint() and driver.checkpoint()==dr.checkpoint();assert len(driver.submitted)==5;assert len(scene['roster'])==12 and scene['cards']==['unit/ch7/predefined/mine/level1'];outcomes=[e for e in s.session.events if e['type'] in ('command.accepted','command.rejected')];assert len(outcomes)==6 and all(e['type']=='command.accepted' for e in outcomes),outcomes;assert s.ctx.resources.current('system/battle','stock_ch7_mine')==14;assert s.ctx.resources.current('public_mine','hp')==100
 for name,value in [('replay',s.export_replay()),('snapshot',s.snapshot()),('driver',driver.checkpoint()),('input',p)]: (out/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
 rep={'passed':True,'core':implementation_digest(),'stage_sha':sha(src),'checkpoint_sha':h,'checkpoint_head_equal':True,'driver_equal':True,'public_ack5':driver.submitted,'public_commands':outcomes,'tick':300,'events':len(s.session.events),'mine_stock':14,'source_native_life':3,'DP':s.ctx.resources.current('system/battle','dp'),'scope':'Native full stage source uncut first300 only. 5actual external ack and actual separate card deploy100 with realDP/stock15→14; fixed12 selected, no claim12actual deploy or mine explosion or stage terminal.','whole_stage_executed':False};f=out/'verification.json';f.write_text(json.dumps(rep,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(f),'events':rep['events']}))
if __name__=='__main__':main()
