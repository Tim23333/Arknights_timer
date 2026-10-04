"""Never-activated source effects vs genuinely launched retired-source packets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m20_peer import probe as h
import json
import hashlib
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim import Engine
from ark_sim.tools.replay import replay
def source_write(channel):
    p=h.fixture();p['entities'][0]['components']['attributes']['base']['atk']=20
    for entity in p['entities']:entity['components']['attributes']['base'].update({'def':0,'mres':0})
    s=h.make(p);assert s.ctx.alive(2) and not s.ctx.active(2) and s.ctx.get(2,('runtime','state'))=='dormant'
    before_rng=s.checkpoint()['kernel']['random']
    effect={'sp':{'op':'modify_resource','resource':'sp','delta':3},'damage':{'op':'damage','damage_type':'physical','scale':1},
      'random':{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'emit','event':'dormant.source.random'}]}}[channel]
    s.ctx.effects.execute(2,['director'],effect)
    actual={'hp':s.ctx.resources.current('director','hp'),'sp':s.ctx.resources.current('director','sp'),
      'rng_unchanged':s.checkpoint()['kernel']['random']==before_rng,
      'damage_events':[thaw(e) for e in s.session.events if e['type']=='damage.accepted'],
      'random_events':[thaw(e) for e in s.session.events if e['type']=='random.branch']}
    assert actual['hp']==50 and actual['sp']==10 and actual['rng_unchanged'] and not actual['damage_events'] and not actual['random_events'],repr(actual)
def real_launched_packet_survives_opt_in_source_death():
    p=h.fixture();p['entities'][0]['components']['attributes']['base']['atk']=20
    for entity in p['entities']:entity['components']['attributes']['base'].update({'def':0,'mres':0})
    p['entities'][0]['components']['abilities'].append('ability/launched')
    p['abilities'].append({'id':'ability/launched','kind':'ability','activation':{'mode':'manual'},'parameters':{'projectile_speed':10},
      'timeline':[{'at':0,'effect':{'op':'damage','target':3,'damage_type':'physical','scale':1,
         'read_mode':{'source_attributes':'at_launch','target_attributes':'at_hit'}}}]})
    p['entities'][1]['components']['abilities'].append('ability/retire_source')
    p['abilities'].append({'id':'ability/retire_source','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'retire','target':2,'parameters':{'reason':'dead'}}]},'timeline':[]})
    s=h.make(p);h.command(s,'ability/activate',0)
    s.submit({'action':'skill','source':2,'ability':'ability/launched'},at=1);h.command(s,'ability/retire_source',2)
    s.advance(3);assert not s.ctx.active(2) and s.ctx.get(2,('runtime','state'))=='dead'
    assert s.ctx.resources.current('director','hp')==50
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    cp=s.checkpoint();s.advance(5);assert s.ctx.resources.current('director','hp')==30
    hit=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hit)==1 and hit[0]['time']==7 and hit[0]['payload']['amount']==20
    r=Engine.restore(s.program,cp);r.advance(5);assert r.snapshot()==s.snapshot()==replay(s.program,s.export_replay()).snapshot()
if __name__=='__main__':
    core=implementation_digest();files=[Path(__file__),Path(h.__file__)]
    start={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};cases=[]
    for name,fn in [('inactive_source_sp',lambda:source_write('sp')),('inactive_source_damage',lambda:source_write('damage')),
       ('inactive_source_random',lambda:source_write('random')),('genuine_retired_source_packet',real_launched_packet_survives_opt_in_source_death)]:
        h.LAST=None
        try:fn();c={'case':name,'result':'passed'}
        except Exception as e:c={'case':name,'result':'failed','error':repr(e)}
        if h.LAST is not None:
            s=h.LAST;c.update({'API_only':name!='genuine_retired_source_packet','program':s.program.fingerprint,'runtime':s.runtime_fingerprint,
              'initial_scenario':thaw(s.program.scenario),'commands':s.export_replay(),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events]})
        cases.append(c)
    end={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    out=h.ROOT/'validation/campaign/m20_dormant_source_db6134_complete.json';out.write_text(json.dumps({'provisional':True,'formal_approval':False,
       'core_start':core,'core_end':implementation_digest(),'source_start':start,'source_end':end,'runtime_module':h.ark_sim.__file__,'cases':cases},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core_start':core,'core_end':implementation_digest(),'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
