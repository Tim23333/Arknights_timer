"""Additional original skill/SP policy, 15 receiver mount and redeploy gates."""
import copy,json,gc,traceback,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.campaign_elemental_receiver_peer_v1 import verify as v
from tools.campaign_elemental_receivers_v1.build import mount
from ark_sim.adapters.api import implementation_digest
def prior_freeze():
    d,t,src,_=v.package()
    rid='rule/peer/prior_freeze';d['definitions'].append({'id':rid,'kind':'rule','contract':'resource.recovery_freeze','implementation':{'type':'expression','expression':'True'}})
    t['components']['resources']['sp']['recovery_freeze_rule']=rid
    v.packet(d,src,'DARK',1000,9)
    v.effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','value':18},3)
    for tick in (6,12,461):v.effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','delta':1,'parameters':{'respect_recovery_freeze':True}},tick)
    s=v.cpp(v.make(v.finish(d,t),'prior_freeze'),40,463,'prior_freeze')
    assert v.sp(s)==3
    assert {6,12,461}<={e['time'] for e in v.events(s,'resource.recovery_suppressed')}
    v.FACTS['prior_freeze']={'SP':v.sp(s),'suppressed':[e['time'] for e in v.events(s,'resource.recovery_suppressed')]}
def ongoing_skill():
    d,t,src,by=v.package('unit/char_151_myrtle',isolate=False)
    by['ability/char_151_myrtle/normal_attack']['activation']['condition']='False'
    d['scenarioDraft']['resources']={'dp':{'initial':100,'capacity':200}}
    v.effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','value':24},3)
    d['scenarioDraft']['commands'].append({'at':5,'action':'skill','source':'receiver','ability':'ability/campaign_myrtle_s2'})
    v.packet(d,src,'DARK',1000,9)
    v.effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','delta':3,'parameters':{'respect_recovery_freeze':True}},470)
    s=v.make(v.finish(d,t),'original_skill');s.advance(470)
    casts=s.ctx.get('receiver',('runtime','casts'));assert any(c['ability']=='ability/campaign_myrtle_s2' for c in casts.values())
    assert v.state(s)['break'] is None and v.sp(s)==0
    s=v.cpp(s,470,520,'original_skill')
    assert any(e['time']==470 for e in v.events(s,'resource.recovery_suppressed'))
    assert not s.ctx.get('receiver',('runtime','casts')) and v.sp(s)>0
    dp=s.ctx.resources.current('system/battle','dp');assert dp==116
    v.FACTS['ongoing_original_skill']={'retained_through_dark_end':True,'DP':dp,'SP520':v.sp(s),'HP':v.hp(s)}
def all15():
    d,t,src,by=v.package()
    original={k:copy.deepcopy(row) for k,row in by.items() if row['kind']=='entity'}
    assert len(original)==15
    mount(d,entities=list(original))
    for key,old in original.items():
        now=by[key]
        assert now['components']['resources']['hp']==old['components']['resources']['hp']
        assert now['components'].get('abilities')==old['components'].get('abilities')
        if 'sp' in old['components']['resources']:
            new_sp=copy.deepcopy(now['components']['resources']['sp']);new_sp.pop('recovery_freeze_rule',None)
            old_sp=copy.deepcopy(old['components']['resources']['sp']);old_sp.pop('recovery_freeze_rule',None)
            assert new_sp==old_sp
        assert now['components']['elemental']['elements']['FIRE']['capacity']==1000
    # Separately construct actual independent token receiver, without replacing
    # its source components, to verify explicit 15-entity scope includes summons.
    facts=[]
    for target in ('unit/campaign_weedy_cannon','unit/kalts_mon3tr_model','unit/support_night_bird'):
        probe,actor,sender,_=v.package(target);v.packet(probe,sender,'DARK',113,9)
        s=v.cpp(v.make(v.finish(probe,actor),'summon'),10,15,'summon')
        assert v.state(s)['remaining']['DARK']==887
        facts.append({'definition':target,'remaining':v.state(s)['remaining']['DARK'],'HP':v.hp(s)})
    v.FACTS['all15_mount']={'count':15,'health_SP_abilities_preserved':True,'summons_actual':facts}
def redeploy():
    d,t,src,_=v.package('unit/char_151_myrtle')
    # Real public deployment, withdrawal, full original 70-second cooldown,
    # then public redeployment; target IDs follow actual creation order.
    d['scenarioDraft']['initialEntities']=d['scenarioDraft']['initialEntities'][1:]
    d['scenarioDraft']['roster']=[t['id']]
    d['scenarioDraft']['resources']={'dp':{'initial':200,'capacity':200}}
    d['scenarioDraft']['parameters']={'deploy_capacity':2}
    deploy={'action':'deploy','definition':t['id'],'alias':'receiver','position':{'row':3,'col':3},'facing':'right'}
    d['scenarioDraft']['commands'].append({'at':0,**deploy})
    v.effect(d,src,{'op':'elemental_damage','target':3,'element':'DARK','amount':1000},9)
    d['scenarioDraft']['commands'].append({'at':20,'action':'withdraw','source':'receiver'})
    d['scenarioDraft']['commands'].append({'at':2121,**{**deploy,'alias':'receiver2'}})
    s=v.cpp(v.make(v.finish(d,t),'redeploy'),21,2123,'redeploy')
    assert s.ctx.active('receiver2') and not s.ctx.active('receiver')
    new=s.ctx.get('receiver2',('runtime','elemental'));assert new['remaining']=={'FIRE':1000,'DARK':1000} and new['break'] is None
    assert not s.ctx.get('receiver2',('buffs','instances')) or all(b['definition']!=v.DARK for b in s.ctx.get('receiver2',('buffs','instances')))
    assert s.ctx.resources.current('receiver2','hp')==1565
    v.FACTS['redeploy']={'new_receiver_state':new,'new_HP':s.ctx.resources.current('receiver2','hp'),'old_state':v.state(s),'cooldown_seconds':70,'deploy_ticks':[0,2121]}
def main():
    core=implementation_digest();rows=[]
    for name,fn in [('prior_SP_freeze_composed_after_DARK',prior_freeze),('existing_original_skill_kept_and_SP_freeze',ongoing_skill),('all15_scope_preserves_HP_SP_owned_skills',all15),('actual_public_redeploy_reset',redeploy)]:
        try:fn();rows.append({'case':name,'passed':True})
        except Exception as e:rows.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:print(json.dumps(rows[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/elemental-receiver-independent-peer-extra/v1','cases':rows,'facts':v.FACTS,'actual_CP_head_proofs':v.PROOFS,'implementation':core,'primary_unchanged':implementation_digest()==core,'peer_sha256':v.sha(__file__),'passed':all(r['passed'] for r in rows)}
    path=v.OUT.with_name('extra.v1.json');path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if result['passed'] and result['primary_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
