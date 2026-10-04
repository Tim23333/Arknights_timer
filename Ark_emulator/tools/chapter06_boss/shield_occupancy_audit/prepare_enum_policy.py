"""Independent byte/excerpt check; preserve prior investigation history."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'packages/campaign/chapter06_boss/shield_occupancy_audit'
EXPECTED='450f6d0903b23721b7e4c06f5176a454a67ddc2ac1d3ed33969fafa41a8c7a35'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while chunk:=f.read(1048576):h.update(chunk)
 return h.hexdigest()
def main():
 p=OUT/'enum.mapping.root.v1.json';assert sha(p)==EXPECTED;d=json.loads(p.read_bytes());dump=Path(d['source_path']);assert sha(dump)==d['source_sha256']
 with dump.open(encoding='utf8') as f:
  lines=[]
  for i,line in enumerate(f,1):
   if 435503<=i<=435515:lines.append(line.rstrip())
   if i>435515:break
 assert 'public const TileSelector.FilterType EXCEPT_CHARACTER = 2;' in '\n'.join(lines)
 raw=[]
 for name in ['frstar2','frstar2_s']:
  s=ROOT/'packages/campaign/chapter06_boss'/name/'source.closure.json';v=json.loads(s.read_bytes());cs=v.get('components',v.get('prefab',{}).get('components'))
  for key,c in cs.items():
   if c['native_class']=='TileSelector':
    r=c['raw'];assert type(r['_filterType']) is int and r['_filterType']==2
    raw.append({'boss':name,'pointer':key,'source_sha256':sha(s),'filter_type':r['_filterType'],'target_side_mask':r['_targetSide'],'target_motion_mask':r['_targetMotion'],'target_category_mask':r['_targetCategory']})
 report={'schema':'ark-sim/ch6-shield-enum-author-check/v1','actual_dump_sha256':sha(dump),'enum_report_sha256':EXPECTED,'actual_raw_excerpt':'\n'.join(lines),'native_fields':raw,'correction_to_prior_investigation':'Current local native enum declaration independently confirmsFilterType2=EXCEPT_CHARACTER. Earlier report correctly recorded then-missing evidence and remains historical; no longer call currentmapping onlyhardcoded.','reference_policy':'Capture excludes existing friendlyside0/bit1 CHAR1 independentofdeployable. Later genuine entrants to capturedcells are affected by original55frameInstantKill; source_side_mask interpretation and crossversionbody remain explicitlyreplaceable.','required_actual_cases':['ExistingfriendlyCHAR1 no deployable excluded','Sameunit_type1 side1 not excluded','TOKEN category/unit_type preserved accordingdeclaredpolicy','Inactive/dormant occupant not counted','Publiclateactivation afteracceptedcapture before55frame actuallykilled','DiskCP beforecapture andbetween capture/effect +head'],'runtime_modified':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
 p=OUT/'enum.mapping.author.check.v1.json';p.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(p)}))
if __name__=='__main__':main()
