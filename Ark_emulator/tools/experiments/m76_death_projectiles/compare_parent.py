"""Actual no-profile values against frozen M73, separate interpreters."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'validation/campaign/m76_death_projectiles'

def worker(runtime,path):
    sys.path.insert(0,runtime)
    from ark_sim import Compiler,Engine
    result={}
    for label,package,ticks in [('actual0_1',ROOT/'packages/ark_content/level_main_00_01.json',120),
                              ('custom850',ROOT/'packages/custom/custom_guard.json',30)]:
        sim=Engine.create(Compiler().compile(package),seed=123)
        if label=='actual0_1':
            for item in json.loads((ROOT/'scenarios/level_main_00_01/commands.json').read_text(encoding='utf8')):
                action=dict(item);sim.submit(action,at=action.pop('at'))
        sim.session.advance(ticks)
        result[label]={'snapshot':sim.snapshot(),'checkpoint':sim.checkpoint(),'replay':sim.export_replay(),
                       'effect_phase':sim.ctx.effect_phase,'base_effect_phase':len(sim.program.ruleset.get('system_order',()))+1}
    Path(path).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf8')

def differences(a,b,path=''):
    if type(a) is not type(b):return [{'path':path,'reason':'type'}]
    if isinstance(a,dict):
        result=[]
        for key in sorted(set(a)|set(b)):
            pointer=path+'/'+key.replace('~','~0').replace('/','~1')
            result.extend([{'path':pointer,'reason':'missing'}] if key not in a or key not in b else differences(a[key],b[key],pointer))
        return result
    if isinstance(a,list):
        if len(a)!=len(b):return [{'path':path,'reason':'length'}]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'/'+str(i))]
    if isinstance(a,float):
        import struct
        equal=struct.pack('>d',a)==struct.pack('>d',b)
    else:equal=a==b
    return [] if equal else [{'path':path,'expected':a,'actual':b}]

def main():
    OUT.mkdir(parents=True,exist_ok=True);values=[];runs=[]
    for label,name in [('parent','campaign_m68_deployment_integrated_candidate'),('candidate','campaign_m76_death_projectiles_v7_candidate')]:
        path=OUT/(label+'-no-profile-full-values.json');runtime=ROOT.parent/'unpack_work'/name
        subprocess.run([sys.executable,str(Path(__file__)),'--worker',str(runtime),str(path)],check=True)
        values.append(json.loads(path.read_text(encoding='utf8')))
        runs.append({'label':label,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    actual=differences(*values)
    allowed=sorted('/'+case+'/'+part+'/runtime_fingerprint' for case in values[0] for part in ('snapshot','checkpoint','replay'))
    root_program=sorted('/'+case+'/'+part+'/program_fingerprint' for case in values[0] for part in ('snapshot','checkpoint','replay'))
    import re
    pattern=re.compile(r'^/(actual0_1|custom850)/(snapshot/events|checkpoint/kernel/events/records)/\d+/payload/trace(?:/stages/\d+/trace)*/runtime_fingerprint$')
    unexpected=[d for d in actual if d['path'] not in allowed+root_program and not pattern.fullmatch(d['path'])]
    if unexpected:raise AssertionError({'unexpected_count':len(unexpected),'first':unexpected[:3]})
    if not all(type(d.get('expected')) is str and type(d.get('actual')) is str and len(d['expected'])==len(d['actual'])==64 for d in actual):
        raise AssertionError('Identity differences must be actual64char fingerprint values')
    report={'passed':True,'scope':'Complete actual source0-1 tick120/custom850 tick30 without death emission or completion-blocking opt-in',
            'runs':runs,'differences':actual,'allowed_identity_path_grammar':[allowed,root_program,pattern.pattern],
            'identity_change_reason':'Added catalog contract and pure provider registry change rule/program identities; exact observed paths retained',
            'all_other_values_types_float_bits_and_raw_effect_phase_equal':True}
    (OUT/'no_profile_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'identity_paths':len(actual),'all_other_values_equal':True}))

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2],sys.argv[3])
    else:main()
