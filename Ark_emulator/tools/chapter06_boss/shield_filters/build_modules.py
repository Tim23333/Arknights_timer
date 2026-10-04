"""Exact friendly CHAR capture exclusion on generic projected tile facts."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
ENUM=ROOT/'packages/campaign/chapter06_boss/shield_occupancy_audit/enum.mapping.root.v1.json'
BASES={
 'ordinary':('frstar2_v2/model.v2.json','ff106842ad0e02aeea517c8dcdbeae49abdfc25990ffefed6b30a2cda6673ac2','frstar2_v3'),
 'story':('frstar2_s/model.json','715b2960092d2df2c6a4027f1e5f45c57453d55c00304b57ba2a9ede6432e5d1','frstar2_s_v2')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(which):
 source,pin,dest=BASES[which];old=ROOT/'packages/campaign/chapter06_boss'/source
 if sha(old)!=pin or sha(ENUM)!='450f6d0903b23721b7e4c06f5176a454a67ddc2ac1d3ed33969fafa41a8c7a35':raise ValueError('Frozen source/enum required')
 p=json.loads(old.read_bytes());count=0
 for d in p['definitions']:
  if d['kind']=='ability' and 'tile_selector' in d:
   tile=d['tile_selector'];tile['eligibility_expression']='('+tile['eligibility_expression']+') and [params.character_side, params.character_bit] not in inputs.occupied_side_unit_type_bits';tile['parameters'].update({'character_side':0,'character_bit':1})
   d['metadata']['selection_policy']='Originalradius/buildability/occupancy conditions AND excludes existingprojectedside0/CHARbit1, independentofdeployable. Actuallateentrants aftercapture remain55frameInstantKill; no recheck.'
   d['metadata']['source_conflict']='Currentnativeenum EXACTFilterType2=EXCEPT_CHARACTER. Mapping targetSide1→friendlyside0/bit1 is explicitreference, crossversionbody unverified; PRTS lateoccupant wording compatible.'
   count+=1
 if count!=(2 if which=='ordinary' else 1):raise ValueError('All exact Shield variants required')
 meta=p['manifest']['metadata'];meta['source_locks'][str(old.relative_to(ROOT))]=pin;meta['source_locks'][str(ENUM.relative_to(ROOT))]=sha(ENUM);meta['builder_sha256']=sha(Path(__file__));meta['reference_policies']['tile_filter']='NativeEXCEPT_CHARACTER2 verifiedcurrentdump; capture excludes actualfriendlyside0 CHARbit1 inclnondeployableNPC andcompositemasks. Originalbuildability/deployment occupancy remain; sideMask interpretation/crossversionbody replaceable. Capturedlateentrant55framekill remains.';meta['required_generic_tile_fact']='occupied_side_unit_type_bits';meta['generic_independently_reviewed']=False
 out=ROOT/'packages/campaign/chapter06_boss'/dest;out.mkdir(exist_ok=True);path=out/'model.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());return path
if __name__=='__main__':
 for which in BASES:
  p=build(which);print(json.dumps({'which':which,'path':str(p),'sha256':sha(p)}))
