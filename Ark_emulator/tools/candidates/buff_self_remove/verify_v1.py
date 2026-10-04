"""Self-remove lifetime behavior and strict unchanged construction-cycle rules."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def model():
    return {'schemaVersion':2,'manifest':{'id':'package/selfremove_probe','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/selfremove','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':10}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'buffs':{'initial':['buff/selfremove']}}}],
        'buffs':[{'id':'buff/selfremove','kind':'buff','interval_seconds':.1,'effects':[
            {'op':'modify_resource','resource':'hp','delta':-3},{'op':'remove_buff','buff':'buff/selfremove'}]}],
        'scenarioDraft':{'id':'scene/selfremove','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},
            'initialEntities':[{'definition':'unit/selfremove','instanceAlias':'unit','position':{'row':0,'col':0}}]}}


def main():
    assert implementation_digest()=='1cb64a004d15f0b365c0affc02ad900444cd9e5ca263707f7c176c3f3bd1c4fd'
    p=model();s=Engine.create(Compiler().compile(p),seed=61723);s.session.advance(2)
    out=ROOT/'validation/campaign/buff_self_remove_v1/proof';assert not out.exists();out.mkdir(parents=True)
    cp=out/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.session.advance(12);r.session.advance(12);head=replay(s.program,s.export_replay())
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and s.ctx.resources.current('unit','hp')==97
    assert s.ctx.get('unit',('buffs','instances'))==[]
    assert len([e for e in s.session.events if e['type']=='buff.removed'])==1
    cases=[{'case':'once periodic removes actual own instance with CP/head','passed':True}]
    for name,change in [('self_apply',lambda p:p['buffs'][0]['effects'].append({'op':'apply_buff','buff':'buff/selfremove'})),
                        ('missing_remove',lambda p:p['buffs'][0]['effects'][1].update(buff='buff/missing')),
                        ('entity_remove',lambda p:p['buffs'][0]['effects'][1].update(buff='unit/selfremove'))]:
        bad=deepcopy(p);change(bad)
        try:Compiler().compile(bad)
        except ValueError:cases.append({'case':name,'rejected':True})
        else:raise AssertionError(name)
    bad=deepcopy(p);bad['buffs'][0]['effects'][1]['buff']='buff/other';bad['buffs'].append({'id':'buff/other','kind':'buff','effects':[{'op':'apply_buff','buff':'buff/selfremove'}]})
    try:Compiler().compile(bad)
    except ValueError:cases.append({'case':'mutual construction cycle','rejected':True})
    else:raise AssertionError('mutual cycle')
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cases':cases,'cp_sha':pin,
        'scope':'Author exact own-instance removal exemption only; all other dependency validation preserved; independent/fullsuite pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'cases':len(cases),'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
