"""Check untouched independently saved source counter-inputs against v7."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter06_review.stage_converter_v7 import compose,exact


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'validation/campaign/chapter06_adapter_v6_independent'
    ip=base/'inputs.json';vp=base/'verification.json';inputs=json.loads(ip.read_bytes());prior=json.loads(vp.read_bytes())['cases']
    stories={c['metadata']['native_story_key']:c for c in json.loads((ROOT/'packages/campaign/chapter06_npcs/story_controls.v2.model.json').read_bytes())['controls']}
    files=[ip,vp,Path(__file__),ROOT/'tools/chapter06_review/stage_converter_v7.py',ROOT/'tools/chapter06_review/stage_converter_v6.py']
    before={str(p):sha(p) for p in files};rows=[];outputs=[]
    for idx,(data,expectation) in enumerate(zip(inputs,prior)):
        try:
            scene,controls=compose(data['native'],'level_main_06-15',{'enemy_1510_frstar2_s':{'unit':'unit/peer/explicit_pending_boss','motion':'WALK'}},{},
                story_controls=stories,predefined_profile=data['pre'],story_key_profile=data['profile'],action_lifecycle_profiles=data['exits'])
        except ValueError:
            assert idx!=0;rows.append({'case':expectation['name'],'rejected':True,'passed':True});outputs.append(None)
        else:
            assert idx==0;assert exact(scene['initialEntities'],data['pre']['initial_entities'])
            rows.append({'case':expectation['name'],'passed':True});outputs.append({'scene':scene,'controls':controls})
    after={str(p):sha(p) for p in files};assert before==after and len(rows)==15
    out=ROOT/'validation/campaign/chapter06_converter_v7_saved_inputs';out.mkdir(exist_ok=False)
    (out/'outputs.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report={'passed':True,'cases':rows,'guards_start':before,'guards_end':after,'scope':'All original15 independent input expectations unchanged; recursive type-exact binding repair, no stage compile/run claim'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
