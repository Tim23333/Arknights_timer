"""Independent endpoint arithmetic and strict NPC no-skill/profile failures."""
from copy import deepcopy
from fractions import Fraction
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT))
from tools.chapter06_npcs.normalize_inputs import normalized


def main():
    source=json.loads((ROOT/'packages/campaign/chapter06_predefines/source.reference.json').read_bytes())
    output=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json';data=json.loads(output.read_bytes());results=[]
    expected={'char_002_amiya':(1284,544,113),'char_367_swllow':(1306,448,135),'char_017_huang':(2305,631,321)}
    for raw in source['stages']['level_main_06-15']['instances']:
        key=raw['raw_native']['inst']['characterKey'];row=next(r for r in data['records'] if r['character_id']==key)
        assert (row['stats']['maxHp'],row['stats']['atk'],row['stats']['def'])==expected[key]
        frames=raw['raw_character']['phases'][2]['attributesKeyFrames'];lo,hi=frames[0],frames[-1]
        for attr,value in zip(['maxHp','atk','def'],expected[key]):
            exact=Fraction(str(lo['data'][attr]))+(Fraction(str(hi['data'][attr]))-Fraction(str(lo['data'][attr])))*Fraction(25-lo['level'],hi['level']-lo['level'])
            # Native zero-favor profile: independent positive half-up arithmetic.
            calculated=(2*exact.numerator+exact.denominator)//(2*exact.denominator)
            assert value==calculated
        assert row['native_instance']==raw['raw_native'] and row['skill_index']==-1 and row['selected_skill'] is None
        assert row['phase']==2 and row['level']==25 and row['favor_point']==row['potential_rank']==0
        results.append({'case':key,'passed':True,'stats':expected[key]})
        for name,change in [('bool_skill',lambda x:x['raw_native'].update(skillIndex=True)),
                            ('selected_skill_zero',lambda x:x['raw_native'].update(skillIndex=0)),
                            ('bool_level',lambda x:x['raw_native']['inst'].update(level=True)),
                            ('wrong_favor',lambda x:x['raw_native']['inst'].update(favorPoint=100))]:
            altered=deepcopy(raw);change(altered)
            try:normalized(altered)
            except ValueError:results.append({'case':key+'/'+name,'rejected':True})
            else:raise AssertionError(name)
    out=ROOT/'validation/campaign/chapter06_npc_inputs_v1';assert not out.exists();out.mkdir(parents=True)
    p=out/'verification.json';p.write_text(json.dumps({'passed':True,'cases':results,'input_sha':hashlib.sha256(output.read_bytes()).hexdigest(),
        'scope':'Independent rational endpoint/interpolation and no-skill/config schema checks; native rounding calibration remains reference policy'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'cases':len(results),'sha':hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
