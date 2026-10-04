"""Preserve complete minimum public-content callback failures on frozen M73."""
from pathlib import Path
import hashlib,json
from test_peer import ROOT,RUNTIME,scene,make,events
from ark_sim.adapters.api import implementation_digest
from tools.campaign_ordered_checkpoint import write_ordered

def main():
    out=ROOT/'validation/campaign/m73_environment_peer/callback_reproduction';out.mkdir(parents=True,exist_ok=True)
    before=implementation_digest();assert before=='1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932'
    rows=[]
    for name,callback in [('retire_second',{'op':'retire','target':3,'parameters':{'reason':'withdrawn'}}),
                           ('move_second',{'op':'move','target':3,'position':{'row':0,'col':1}})]:
        package=scene(callback=callback);sim=make(package)
        fixture=out/(name+'-fixture.json')
        with fixture.open('x',encoding='utf8') as file:json.dump(package,file,ensure_ascii=False,indent=2);file.write('\n')
        sim.session.advance(2)
        cp=out/(name+'-before-checkpoint.json');cp_sha=write_ordered(cp,sim.checkpoint())
        sim.session.advance(2)
        result=out/(name+'-after-full-values.json')
        with result.open('x',encoding='utf8') as file:json.dump({'snapshot':sim.snapshot(),'checkpoint':sim.checkpoint(),'replay':sim.export_replay()},file,ensure_ascii=False,indent=2);file.write('\n')
        rows.append({'case':name,'before_checkpoint_sha256':cp_sha,'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'actual_second_hp':sim.ctx.resources.current('second','hp'),'required_second_hp':2000,
            'second_runtime':sim.ctx.get('second',('runtime',)), 'second_position':sim.ctx.get('second',('spatial','position')),
            'event_order':[{'id':e['id'],'time':e['time'],'type':e['type'],'target':e['payload'].get('target')}
                for e in sim.session.events if e['type'] in ('field.triggered','damage.accepted','entity.withdrawn','entity.displaced')],
            'complete_values_sha256':hashlib.sha256(result.read_bytes()).hexdigest()})
    assert implementation_digest()==before
    report={'core_start':before,'core_end':implementation_digest(),'cases':rows,'runtime_bug_reproduced':True,
        'scope':'Normal authored damage.accepted ability subscription; no monkeypatch or frozen-source edit'}
    with (out/'reproduction.json').open('x',encoding='utf8') as file:json.dump(report,file,ensure_ascii=False,indent=2);file.write('\n')
    print(json.dumps(report))

if __name__=='__main__':main()
