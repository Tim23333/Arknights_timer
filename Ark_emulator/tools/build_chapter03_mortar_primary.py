"""Distinct source flag consumer revision, requires M59 include_primary."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter03_models/mortar.targeting.reference.json';PIN='3d205d2d3c673d63b2380073c2bbf1db292d1f3bf11321a27104033f8575c8fe';OUT=ROOT/'packages/campaign/chapter03_models/mortar.primary.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 if sha(PARENT)!=PIN:raise ValueError('frozen Mortar targeting profile drift')
 p=json.loads(PARENT.read_bytes());meta=p['manifest']['metadata'];raw=meta['raw_source'];assert raw['simple']['_alwaysHitTraceTargetInTheEnd']==1 and raw['hit']['_targetOptions']['ignoreTargetFree']==0
 for rule in p['rules']:
  if rule['contract']=='area.members':rule['parameters']['include_primary']=True
 meta['source_locks'][str(PARENT.relative_to(ROOT))]=PIN;meta.update(primary_builder_sha256=sha(Path(__file__)),required_runtime_feature='qualified area include_primary captured/legal candidate union')
 meta['profiles']['primary']='Source alwaysHitTraceTargetInEnd1 plus reference forced primary: include captured actor outside impact grid only if still domain active/visible/available and sourceHit typed eligibility permits it. Grid members and primary union once. Reached/expiry use same explicit policy.'
 meta['feedback_pending']=[('INVISIBLE9 is available through explicit actor-bound M49 targeting.availability; include-primary is not a default9 writer or bypass' if text=='INVISIBLE9 availability requires M49 merge; forceIgnoreCamouflage17 does not grant9 immunity' else text) for text in meta['feedback_pending']]
 meta['feedback_pending'] += ['Forced captured primary now has mathematical consumer; native ordering/invalid callback remains feedback','M55/M57 obstacle contact is external integration; standalone M59 source9 availability is available but route_obstacle schema not imported']
 p['manifest']['id']+='/include_primary';return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('stale Mortar include-primary profile')
 else:OUT.write_bytes(raw)
 print(json.dumps({'sha256':sha(OUT)}))
