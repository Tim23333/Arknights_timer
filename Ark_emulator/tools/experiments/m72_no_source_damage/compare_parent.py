"""No-opt actual source full-value comparison in separate interpreters."""
from pathlib import Path
import hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'validation/campaign/m72_no_source_damage'

def worker(runtime,path):
    sys.path.insert(0,runtime)
    from ark_sim import Compiler,Engine
    result={}
    for label,package,ticks in [('source0_1',ROOT/'packages/ark_content/level_main_00_01.json',120),
                              ('custom850',ROOT/'packages/custom/custom_guard.json',30)]:
        program=Compiler().compile(package);sim=Engine.create(program,seed=123)
        if label=='source0_1':
            for item in json.loads((ROOT/'scenarios/level_main_00_01/commands.json').read_text(encoding='utf8')):
                action=dict(item);sim.submit(action,at=action.pop('at'))
        sim.session.advance(ticks)
        result[label]={'snapshot':sim.snapshot(),'checkpoint':sim.checkpoint(),'replay':sim.export_replay()}
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
    OUT.mkdir(parents=True,exist_ok=True)
    values=[];runs=[]
    for label,name in [('parent','campaign_m68_deployment_integrated_candidate'),('candidate','campaign_m72_no_source_damage_candidate')]:
        runtime=ROOT.parent/'unpack_work'/name;path=OUT/(label+'-no-opt-full-values.json')
        subprocess.run([sys.executable,str(Path(__file__)),'--worker',str(runtime),str(path)],check=True)
        values.append(json.loads(path.read_text(encoding='utf8')))
        runs.append({'label':label,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    actual=differences(*values)
    allowed=sorted('/'+case+'/'+part+'/'+identity for case in values[0]
        for part in ('snapshot','checkpoint','replay') for identity in ('program_fingerprint','runtime_fingerprint'))
    assert sorted(d['path'] for d in actual)==allowed,actual
    report={'passed':True,'scope':'No opt-in; complete values for actual source0-1 tick120 and custom tick30',
        'runs':runs,'differences':actual,'all_other_values_types_and_float_bits_equal':True}
    (OUT/'no_opt_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2],sys.argv[3])
    else:main()
