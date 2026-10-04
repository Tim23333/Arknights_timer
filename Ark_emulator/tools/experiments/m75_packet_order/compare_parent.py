"""Actual no-profile values against frozen M73, separate interpreters."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'validation/campaign/m75_packets'

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
    for label,name in [('parent','campaign_m73_environment_integrated_v2_candidate'),('candidate','campaign_m75_periodic_packets_candidate')]:
        path=OUT/(label+'-no-profile-full-values.json');runtime=ROOT.parent/'unpack_work'/name
        subprocess.run([sys.executable,str(Path(__file__)),'--worker',str(runtime),str(path)],check=True)
        values.append(json.loads(path.read_text(encoding='utf8')))
        runs.append({'label':label,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    actual=differences(*values)
    allowed=sorted('/'+case+'/'+part+'/runtime_fingerprint' for case in values[0] for part in ('snapshot','checkpoint','replay'))
    assert sorted(d['path'] for d in actual)==allowed,actual
    report={'passed':True,'scope':'Complete actual source0-1 tick120/custom850 tick30 without periodic profiles',
            'runs':runs,'differences':actual,'all_other_values_types_float_bits_and_raw_effect_phase_equal':True}
    (OUT/'no_profile_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2],sys.argv[3])
    else:main()
