import sys,json,copy,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/chapter09_duspfr_v1'))
from test_author import *
def reject(s,cp):
    try:Engine.restore(s.program,cp,providers=providers())
    except (ValueError,KeyError) as error:return str(error)
    raise AssertionError('Invalid lifecycle authority checkpoint restored')
def locate(checkpoint,alias='pillar'):
    actor_id=checkpoint['kernel']['world']['aliases'][alias]
    return next(e for e in checkpoint['kernel']['world']['entities'] if e['id']==actor_id)
def setup():
    p=fixture(pillar_actor=True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/duspfr/test/lethal'}];s=sim(p);s.advance(38);assert s.ctx.resources.current('pillar','hp')==4500;return s,cp(s)
def missing_and_orphan():
    s,checkpoint=setup();r=Engine.restore(s.program,checkpoint,providers=providers());s.advance(50);r.advance(50);assert cp(s)==cp(r)
    for change in ['lease','reset','entire','health']:
        bad=copy.deepcopy(checkpoint);entity=locate(bad);runtime=entity['components']['runtime']
        if change=='lease':runtime['depletion']['lease']=None
        elif change=='reset':runtime['depletion']={'generation':0,'stage':'normal','lease':None};runtime['casts']={}
        elif change=='entire':runtime.pop('depletion')
        else:entity['components']['resources']['hp']['current']=4499
        reject(s,bad)
def source_event_identity_and_fingerprint():
    s,checkpoint=setup();source=locate(checkpoint,'source');cast=next(iter(source['components']['runtime']['casts'].values()))
    for change in ['borrow','value','fp','time','cause','stamp']:
        bad=copy.deepcopy(checkpoint);owner=locate(bad,'source');c=next(iter(owner['components']['runtime']['casts'].values()));event=bad['kernel']['events']['records'][c['depletion_timing_source_event']-1]
        if change=='borrow':c['depletion_timing_source_event']=next(iter(locate(bad)['components']['runtime']['casts'].values()))['depletion_timing_source_event']
        elif change=='value':event['payload']['view']['components']['attributes']['base']['atk']=999
        elif change=='fp':c['depletion_timing_source_fingerprint']='0'*64
        elif change=='time':event['time']+=1
        elif change=='cause':event['cause']=None
        else:event['payload']['view']['components']['runtime']['lifecycle_generation']=17
        reject(s,bad)
def raw_update_no_positive_authority():
    s=sim(fixture(pillar_actor=True));s.ctx.effects.execute('source',['pillar'],{'op':'apply_buff','buff':pillar.READY});owner=s.session.world.resolve('pillar');actor=s.session.world.resolve('source');effect={'op':'damage','damage_type':'true','scale':1}
    with s.ctx.depletion.attack(actor,owner,effect):s.ctx.resources.adjust(owner,'hp',-500,source=actor,settlement_context={'operation':'damage','source':actor,'target':owner,'resource':'hp','ability':None,'cast':None})
    assert s.ctx.resources.current(owner,'hp')==4500 and s.ctx.depletion.state(owner)['generation']==0 and not s.ctx.get(owner,('runtime','casts'),{})
    r=Engine.restore(s.program,cp(s),providers=providers());assert cp(s)==cp(r)
def legitimate_positive_withdraw():
    s,checkpoint=setup();s.ctx.lifecycle.retire('pillar','withdrawn');assert s.ctx.resources.current('pillar','hp')==4500;r=Engine.restore(s.program,cp(s),providers=providers());s.advance(50);r.advance(50);assert cp(s)==cp(r)
def main():
    before=implementation_digest();results=[]
    for fn in [missing_and_orphan,source_event_identity_and_fingerprint,raw_update_no_positive_authority,legitimate_positive_withdraw]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    report={'core_before':before,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results};(OUT/'author.restore.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
