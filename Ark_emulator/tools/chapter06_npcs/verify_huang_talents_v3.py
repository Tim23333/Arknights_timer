"""Public incoming damage witnesses actual heal/one-shot/lock/expiry and replay."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_npcs.build_huang_talents import PARENT,LOCK


def main():
    source=ROOT/'packages/campaign/chapter06_npcs/huang_talents.v3.model.json';p=json.loads(source.read_bytes())
    row=next(r for r in json.loads((ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json').read_bytes())['records'] if r['character_id']=='char_017_huang');stats=row['stats']
    p['entities']=[{'id':'unit/npc_probe/huang','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'max_hp':stats['maxHp'],'atk':stats['atk'],'def':stats['def'],'mres':0,'one_minus_status_resistance':1}},
        'resources':{'hp':{'initial':2305,'capacity':2305,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},
        'buffs':{'initial':[PARENT,'buff/ch6/npc/huang_resistance_wait']}}},
        {'id':'unit/npc_probe/attacker','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'atk':10000,'max_hp':100}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/npc_probe/hit']}}]
    p['selectors']=[{'id':'selector/npc_probe/player','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}]
    p['abilities']=[{'id':'ability/npc_probe/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/npc_probe/player',
        'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
    p['scenarioDraft']={'id':'scene/npc_probe/huang_once','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'objectives':{},
        'initialEntities':[{'definition':'unit/npc_probe/huang','instanceAlias':'huang','position':{'row':0,'col':0}},
            {'definition':'unit/npc_probe/attacker','instanceAlias':'attacker','position':{'row':0,'col':1}}]}
    out=ROOT/'validation/campaign/chapter06_npc_huang_talents_v3';assert not out.exists();out.mkdir(parents=True)
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='')
    core=implementation_digest();s=Engine.create(Compiler().compile(p),seed=61719)
    for tick in [10,20,191]:s.submit({'action':'skill','source':'attacker','ability':'ability/npc_probe/hit'},at=tick)
    s.session.advance(12)
    assert s.ctx.alive('huang') and s.ctx.resources.current('huang','hp')==1153.5
    buffs=s.ctx.get('huang',('buffs','instances'));assert not any(b['definition']==PARENT for b in buffs)
    assert any(b['definition']==LOCK and b['expires_at']==190 for b in buffs)
    cp=out/'lock.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(s.program,load_bound(cp,pin))
    for sim in (s,restored):sim.session.advance(178)
    assert s.ctx.resources.current('huang','hp')==1152.5
    for sim in (s,restored):sim.session.advance(3)
    assert not s.ctx.alive('huang') and s.ctx.resources.current('huang','hp')==0
    head=replay(s.program,s.export_replay());assert s.checkpoint()==restored.checkpoint()==head.checkpoint()
    heals=[e for e in s.session.events if e['type']=='regeneration.accepted'];assert len(heals)==1
    report={'passed':True,'core':core,'module_sha':hashlib.sha256(source.read_bytes()).hexdigest(),'checkpoint_sha':pin,
        'first_post_trigger_hp':1153.5,'during_lock_hp':1152.5,'expired_second_lethal_dead':True,'heals':1,'head_equal':True,
        'scope':'Source lowHP/once-only heal/6s HP floor only; maxHP static native2305, resistance/attack/full NPC separate'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
