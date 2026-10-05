"""Actual primary gaps, before any bloodline kernel change."""
import sys,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE,SWITCHES
OUT=ROOT/'validation/campaign/chapter10_bloodline_v1';OUT.mkdir(parents=True,exist_ok=True)
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
def eligibility(i,p,c):return {'accepted':i['source']['components']['runtime'].get('blocked_by')==i['candidate']['id'],'reason':'actual_blocker'}
def unit(name,hp,block=1):return {'id':'unit/'+name,'kind':'entity','tags':['enemy'] if name!='blocker' else ['player'],'components':{'attributes':{'base':{'max_hp':hp,'atk':100,'def':0,'mres':0,'move_speed':1,'block_count':block,'block_cost':1}},'resources':{'hp':{'role':'health','capacity':hp,'initial':hp}},'spatial':{},'selection_state':{'side':0 if name=='blocker' else 1,'category':1,'motion':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def aura_counter():
    src=unit('source',1500);src['components']['buffs']={'initial':['buff/parent']}
    player=unit('blocker',7000);player['components']['deployable']={'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0}
    p={'schemaVersion':2,'entities':[src,player],'buffs':[{'id':'buff/bonus','kind':'buff','stacking':{'mode':'refresh','max_stacks':1,'identity':['definition','target']},'modifiers':[{'attribute':'block_count','layer':'flat','value':1}]},{'id':'buff/parent','kind':'buff','aura':{'selector':'selector/blocker','buff':'buff/bonus','lease_policy':{'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject'}}}],
       'rules':[{'id':'rule/blocker','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'counter/blocker'}}],
       'selectors':[{'id':'selector/blocker','kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'eligibility':{'rule':'rule/blocker','parameters':{'source_configuration':{**{k:0 for k in SWITCHES},'_targetSide':2,'_targetCategory':1,'_targetMotion':1},'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULT_STATE}}}],
       'scenarioDraft':{'id':'scene/counter/blocker','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':6},'initialEntities':[{'definition':'unit/blocker','instanceAlias':'blocker','position':{'row':0,'col':1}}]+[{'definition':'unit/source','instanceAlias':'source'+str(i),'position':{'row':0,'col':1},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':5},'checkpoints':[]}} for i in range(2)]}}
    reg={**BUILTIN_PROVIDERS,'counter/blocker':{'callable':eligibility,'version':'actual-blocker-1'}};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.advance(2)
    actual=s.ctx.attributes.value('blocker','block_count');children=s.ctx.get('blocker',('buffs','instances'));row={'expected_block_count':3,'actual_block_count':actual,'children':thaw(children),'actual_blocked_by':[s.ctx.spatial.blocked_by('source'+str(i)) for i in range(2)]};assert len(children[0]['aura_leases'])==2 and actual==2;return row
def death_counter():
    parent=unit('parent',4500);parent['components']['buffs']={'initial':['buff/death']};player=unit('blocker',7000);player['components']['abilities']=['ability/kill']
    p={'schemaVersion':2,'entities':[parent,player,unit('child',1500)],'buffs':[{'id':'buff/death','kind':'buff','removal':{'on_target_death':'retain','on_source_death':'retain'},'events':[{'event':'entity.died','effects':[{'op':'schedule','delay_seconds':1,'effect':{'op':'spawn','definition':'unit/child'}}]}]}],
       'selectors':[{'id':'selector/parent','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}],
       'abilities':[{'id':'ability/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/parent','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':50}}]}],
       'scenarioDraft':{'id':'scene/counter/death','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':6},'objectives':{'type':'waves','life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':'unit/blocker','instanceAlias':'player','position':{'row':1,'col':0}}],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/parent','instanceAlias':'parent','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':5},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':0,'col':0}}]}},'count':1,'managed':True,'blocks_wave':True}]}]},{'fragments':[]}]},'commands':[{'at':7,'action':'skill','source':'player','ability':'ability/kill'}]}}
    s=Engine.create(Compiler().compile(p));s.advance(40);children=[e['id'] for e in s.session.world.entities() if e['definition_id']=='unit/child'];diagnostic={'children':children,'kills':s.ctx.state()['kills'],'parent_hp':s.ctx.resources.current('parent','hp'),'parent_alive':s.ctx.alive('parent'),'state':thaw(s.ctx.state()),'events':[thaw(e) for e in s.session.events if e['type']in ['ability.started','damage.accepted','effect.inactive_rejected','entity.died','entity.exited']]};(OUT/'death.actual.diagnostic.v2.json').write_text(json.dumps(diagnostic,indent=2)+'\n',encoding='utf8');assert s.ctx.state()['kills']==1 and s.ctx.state()['timeline']['wave_index']==2 and all(s.ctx.get(child,('spatial','route')) is None for child in children)
    return {'expected_delayed_managed_route_child':1,'actual_children':children,'child_routes':[s.ctx.get(child,('spatial','route')) for child in children],'child_membership':[thaw(s.ctx.state()['timeline']['members'].get(str(child))) for child in children],'immediate_parent_kills':s.ctx.state()['kills'],'battle_finished':s.ctx.state().get('finished'),'timeline':thaw(s.ctx.state()['timeline']),'inactive_rejections':[thaw(e) for e in s.session.events if e['type']=='effect.inactive_rejected']}
def main():
    assert implementation_digest()==CORE;r={'schema':'ark-sim/bloodline-primary-counter/v1','core_before':CORE,'aura_stack':aura_counter(),'death_spawn':death_counter(),'core_after':implementation_digest(),'raw_simulation_artifacts_written':False};p=OUT/'primary.counter.v1.json';assert not p.exists();p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'core':CORE,'actual_gaps_recorded':2}));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        import traceback
        path=OUT/'fixture.failure.v4.json';assert not path.exists();path.write_text(json.dumps({'error':str(error),'traceback':traceback.format_exc()},indent=2)+'\n',encoding='utf8');raise
